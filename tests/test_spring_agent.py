"""Tests for Module A's contract output and the agent wiring. No API key or map layers needed.

Run: python -m pytest tests
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import module_a_vulnerability as module_a  # noqa: E402
import spring_agent  # noqa: E402

EXAMPLE_ID = "ATL-SPR-0199"  # Kimi Nauli, Nainital: an input spring at 1,197 m


class DatasetSession:
    """Stands in for the map layers: returns the dataset's feature row for the example spring."""

    def __init__(self):
        self.row = next(r for r in module_a.read_csv(module_a.FEATURES_CSV) if r["record_id"] == EXAMPLE_ID)
        self.indicators = module_a.load_indicators()
        self.reference, _ = module_a.load_reference()

    def features(self, lat, lon, elevation):
        return {k: v for k, v in self.row.items() if v not in ("", None)}


@pytest.fixture(scope="module")
def session():
    return DatasetSession()


def spring_input(**field):
    return {"spring": {"name": "Kimi Nauli", "latitude": 29.23016, "longitude": 79.63362, "elevation_m": 1197.1}, "field": field}


def test_location_only_is_low_confidence_exposure_score(session):
    out = module_a.assess(spring_input(), session)
    assert out["module"] == "A"
    assert set(out) >= {"spring", "result", "confidence", "rationale", "missing_inputs", "warnings", "report_markdown"}
    assert 0 <= out["result"]["score"] <= 100
    assert out["confidence"] == "Low"
    assert out["missing_inputs"][0]["id"] == "flow_vs_past"
    assert "exposure score" in out["report_markdown"]


def test_field_answers_raise_confidence_and_floor_rule(session):
    out = module_a.assess(spring_input(flow_vs_past="dries_at_times", lean_flow_lpm=0, monsoon_flow_lpm=20, households=30,
                                       low_flow_months=4, users_vs_past="more"), session)
    assert out["result"]["class"] in ("Medium", "High")
    assert out["confidence"] in ("Medium", "High")
    assert any(i["id"] == "flow_vs_past" and i["score"] == 100 for i in out["result"]["indicators"])


def test_bad_answer_is_reported_not_scored(session):
    out = module_a.assess(spring_input(flow_vs_past="sometimes"), session)
    assert not any(i["id"] == "flow_vs_past" for i in out["result"]["indicators"])
    assert any("flow_vs_past" in w for w in out["warnings"])


def test_tool_enums_match_module_a():
    """The agent's tool must offer exactly the answers Module A accepts."""
    tools = {t.name: t.to_dict() for t in spring_agent.make_tools(runner=None)}
    props = tools["assess_vulnerability"]["input_schema"]["properties"]
    assert tools["assess_vulnerability"]["input_schema"]["required"] == ["latitude", "longitude", "elevation_m"]
    for key, (kind, allowed, _) in module_a.OPTIONAL.items():
        assert key in props
        if kind == "choice":
            enum = next(o["enum"] for o in props[key]["anyOf"] if "enum" in o)
            assert enum == allowed, key


def test_find_springs_by_name():
    matches, total = spring_agent.find_springs("kimi nauli")
    assert total >= 1 and matches[0]["record_id"] == EXAMPLE_ID


class StubRunner:
    def __init__(self):
        self.calls = []

    def run(self, inputs):
        self.calls.append(inputs)
        return {"module": "A", "result": {"score": 42.0, "class": "Medium"}, "confidence": "Low", "report_markdown": "long"}


def test_agent_turn_with_mock_api():
    """One turn: the model calls assess_vulnerability, gets the result back, then answers."""
    import anthropic
    import httpx2

    requests = []
    replies = [
        {"content": [{"type": "tool_use", "id": "toolu_1", "name": "assess_vulnerability",
                      "input": {"latitude": 29.23016, "longitude": 79.63362, "elevation_m": 1197.1, "flow_vs_past": "a_bit_less"}}],
         "stop_reason": "tool_use"},
        {"content": [{"type": "text", "text": "Score 42 / 100, Medium."}], "stop_reason": "end_turn"},
    ]

    def handler(request):
        requests.append((request.headers, json.loads(request.content)))
        reply = replies[len(requests) - 1]
        return httpx2.Response(200, json={"id": f"msg_{len(requests)}", "type": "message", "role": "assistant", "model": spring_agent.MODEL,
                                          "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 10}, **reply})

    client = anthropic.Anthropic(api_key="test", base_url="http://test",
                                 http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))
    stub = StubRunner()
    messages = []
    answer = spring_agent.run_turn(client, spring_agent.make_tools(stub), messages, "Score Kimi Nauli", "high")

    assert answer == "Score 42 / 100, Medium."
    assert stub.calls[0]["field"] == {"flow_vs_past": "a_bit_less"}
    headers, first = requests[0]
    assert first["model"] == "claude-opus-5-5"
    assert first["thinking"] == {"type": "adaptive"}
    assert first["output_config"] == {"effort": "high"}
    assert first["fallbacks"] == "default"
    assert spring_agent.FALLBACK_BETA in headers["anthropic-beta"]
    tool_result = requests[1][1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and "report_markdown" not in json.dumps(tool_result)
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]

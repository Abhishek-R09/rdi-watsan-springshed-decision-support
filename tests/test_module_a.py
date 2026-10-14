"""Tests for Module A's output under the shared module contract. No map layers needed.

Run: python -m pytest tests
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import module_a_vulnerability as module_a  # noqa: E402

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
    assert out["status"] == "provisional"


def test_field_answers_raise_confidence_and_floor_rule(session):
    out = module_a.assess(spring_input(flow_vs_past="dries_at_times", lean_flow_lpm=0, monsoon_flow_lpm=20, households=30,
                                       low_flow_months=4, users_vs_past="more"), session)
    assert out["result"]["class"] in ("Medium", "High")
    assert out["confidence"] in ("Medium", "High")
    assert out["status"] in ("complete", "provisional")
    assert any(i["id"] == "flow_vs_past" and i["score"] == 100 for i in out["result"]["indicators"])


def test_bad_answer_is_reported_not_scored(session):
    out = module_a.assess(spring_input(flow_vs_past="sometimes"), session)
    assert not any(i["id"] == "flow_vs_past" for i in out["result"]["indicators"])
    assert any("flow_vs_past" in w for w in out["warnings"])

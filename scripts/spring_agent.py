"""Spring decision-support agent: talks with the user and runs the modules as tools.

The agent collects a spring's location and whatever field answers the user has, calls the modules, and
explains their results in plain language. The modules do all the scoring; the agent explains only what a
tool returned and never makes up a number. Today it runs Module A (vulnerability). Modules B (recharge zone)
and C (DI impact) plug in the same way once they exist: see docs/module-contract.md.

Setup (once)
  pip install -r requirements.txt
  Set ANTHROPIC_API_KEY to an Anthropic API key (console.anthropic.com).
  Module A reads map layers the first time it scores a spring at a new place; --cache and --local-layers
  are the same folders as for scripts/build_spring_features.py.

Usage
  python scripts/spring_agent.py                          chat in the terminal (type "quit" to stop)
  python scripts/spring_agent.py --ask "Score Nauli Dhara in Tehri"     one question, one answer
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Literal, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import module_a_vulnerability as module_a  # noqa: E402

MODEL = "claude-opus-5-5"
# Server-side fallback: if the model declines a request, the API retries it on Anthropic's recommended
# fallback model inside the same call instead of returning a refusal.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16000
MAX_TOOL_ROUNDS = 12
DATASET_MATCHES = 5

SYSTEM_PROMPT = """You help field staff of RDI and WATSAN in the Uttarakhand and Himachal hills judge how vulnerable a mountain spring is.

What vulnerable means here: the spring is declining. It flows less than 10-20 years ago, dries earlier, or has turned from perennial to seasonal. A spring that has always been seasonal is not vulnerable for that reason alone.

How to work:
- To score a spring you need its latitude, longitude and elevation in metres. If any is missing, ask for it. If the user names a spring, you can look it up with find_spring_in_dataset and confirm the match with them before using its coordinates.
- Field answers make the score much more reliable. The most useful one is how the flow now compares with 10-20 years ago, then lean-season flow, households using the spring, and users now vs before. If the user has not given these, ask once for whatever they know, in one short message. Do not hold the score back waiting for them: if they don't know, score with what you have.
- Values found in the dataset (discharge, seasonality) are mostly WATSAN estimates. Before you pass them to assess_vulnerability as field answers, tell the user where they come from and use them only if the user agrees.
- Call assess_vulnerability to get the score. Never estimate a score, a percentile or any other number yourself. Every number you mention must come from a tool result.
- If the decline question was not answered, say clearly that the result is an exposure score: it shows how exposed the spring's setting is, not whether the spring is declining.
- Pass on every warning the tool gives, such as an elevation that does not match the map.

How to explain a result, in simple and plain English:
1. Score out of 100, class (Low, Medium or High) and confidence, in one line.
2. The two or three main reasons, each with its value from the tool.
3. The one or two missing field answers that would change the result most.
4. Where the full report was saved.
Keep it under 200 words unless the user asks for more. Weights and cut-offs are a draft for WATSAN to review; say so if the user asks how firm the result is.

Only Module A (vulnerability) is available now. The recharge zone (Module B) and the DI impact estimate (Module C) are being built separately. If asked for them, say they are not connected yet."""


class ModuleARunner:
    """Keeps Module A's tables and the map layers open across tool calls in one session."""

    def __init__(self, cache, local_layers):
        self.cache, self.local_layers = cache, local_layers
        self.session = None

    def run(self, inputs):
        if self.session is None:
            print("  (Module A: opening the map layers, which takes a few minutes the first time)", file=sys.stderr)
            self.session = module_a.LayerSession(self.cache, self.local_layers)
        output = module_a.assess(inputs, self.session)
        output["report_path"] = str(module_a.save_report(output).relative_to(ROOT))
        return output


def tool_summary(output):
    """The part of a module output the model needs; the long report stays on disk."""
    keep = {k: v for k, v in output.items() if k != "report_markdown"}
    return json.dumps(keep, indent=1, default=lambda v: None if isinstance(v, float) and math.isnan(v) else str(v))


def find_springs(query=None, latitude=None, longitude=None, district=None, limit=DATASET_MATCHES):
    """Springs in the dataset matching a name (and district), or nearest to a coordinate."""
    rows = [r for r in module_a.read_csv(module_a.CLEAN_CSV) if r["coordinate_status"] == "ok"]
    if district:
        rows = [r for r in rows if district.lower() in (r["district"] or "").lower()]
    if query:
        words = query.lower().split()
        rows = [r for r in rows if all(w in (r["spring_name"] + " " + r["village"]).lower() for w in words)]
    if latitude is not None and longitude is not None:
        from build_spring_features import metres_per_degree
        m_lat, m_lon = metres_per_degree(latitude)
        for r in rows:
            r["distance_m"] = round(math.hypot((float(r["latitude"]) - latitude) * m_lat, (float(r["longitude"]) - longitude) * m_lon))
        rows.sort(key=lambda r: r["distance_m"])
    fields = ["record_id", "spring_name", "village", "block", "district", "latitude", "longitude", "elevation_m",
              "seasonality_text", "discharge_dry_lpm", "discharge_monsoon_lpm", "source_dataset", "dataset_split", "distance_m"]
    return [{k: r[k] for k in fields if r.get(k) not in (None, "")} for r in rows[:limit]], len(rows)


def make_tools(runner):
    from anthropic import beta_tool

    @beta_tool
    def find_spring_in_dataset(name: Optional[str] = None, district: Optional[str] = None,
                               latitude: Optional[float] = None, longitude: Optional[float] = None) -> str:
        """Look up springs in the project dataset (1,679 springs in Uttarakhand and Himachal) by name, or find the nearest ones to a coordinate.

        Use it to get a named spring's coordinates and elevation, or to see whether a coordinate is a known spring.
        Discharge and seasonality values in the dataset are mostly WATSAN estimates, not measurements.

        Args:
            name: Spring or village name, or part of it, e.g. "Nauli Dhara".
            district: Optional district to narrow the search, e.g. "Tehri Garhwal".
            latitude: Decimal degrees; give with longitude to list the nearest springs.
            longitude: Decimal degrees; give with latitude.
        """
        if not name and (latitude is None or longitude is None):
            return "Give a name, or both latitude and longitude."
        matches, total = find_springs(name, latitude, longitude, district)
        if not matches:
            return "No spring in the dataset matches. Ask the user for the coordinates and elevation."
        return json.dumps({"matches_shown": len(matches), "matches_total": total, "springs": matches}, indent=1)

    @beta_tool
    def assess_vulnerability(
        latitude: float, longitude: float, elevation_m: float, name: Optional[str] = None,
        flow_vs_past: Optional[Literal["more", "same", "a_bit_less", "much_less", "dries_at_times"]] = None,
        lean_flow_lpm: Optional[float] = None, monsoon_flow_lpm: Optional[float] = None,
        low_flow_months: Optional[float] = None, households: Optional[float] = None,
        users_vs_past: Optional[Literal["fewer", "same", "more", "much_more"]] = None,
        water_quality: Optional[Literal["no_issue", "muddy_after_rain", "contamination"]] = None,
        pollution_30m: Optional[Literal["none", "one", "two_or_more", "latrine"]] = None,
        disturbance_uphill: Optional[Literal["little", "some", "major"]] = None,
        protection: Optional[Literal["both", "one", "neither"]] = None,
        recharge_works: Optional[Literal["maintained", "neglected", "none"]] = None,
        seasonality: Optional[Literal["perennial", "seasonal_perennial", "seasonal", "highly_seasonal", "ephemeral"]] = None,
        spring_type: Optional[str] = None, rock_at_outlet: Optional[str] = None,
    ) -> str:
        """Module A: score how vulnerable (at risk of declining) a spring is, 0-100, with class, confidence and the reason for every point.

        Location, elevation and the map layers give an exposure score. Each field answer adds an indicator; leave out what the user does not know.
        Also writes a one-page report and returns its path.

        Args:
            latitude: Decimal degrees (WGS84).
            longitude: Decimal degrees (WGS84).
            elevation_m: Elevation of the spring in metres (GPS or map).
            name: Spring name, used for the report.
            flow_vs_past: Flow now compared with 10-20 years ago, as the users describe it.
            lean_flow_lpm: Lean-season (May-June) flow in litres per minute; 0 if it dries.
            monsoon_flow_lpm: Monsoon flow in litres per minute.
            low_flow_months: Months a year with low or no flow.
            households: Number of households using the spring.
            users_vs_past: Number of users now compared with 10-20 years ago.
            water_quality: Water quality as observed or reported.
            pollution_30m: Pollution sources within 30 m of the outlet (latrine counts as the worst).
            disturbance_uphill: Roads, fire, grazing or landslides on the slope above the spring.
            protection: Whether the outlet is protected and a user committee is active: both, one or neither.
            recharge_works: Recharge works uphill (trenches, pits, plantation).
            seasonality: How the spring behaves through the year.
            spring_type: Spring type, free text (context only, not scored).
            rock_at_outlet: Rock seen at the outlet, free text (context only, not scored).
        """
        field = {k: v for k, v in locals().items() if k in module_a.OPTIONAL and v is not None}
        print(f"  (running Module A for {name or f'{latitude:.5f}, {longitude:.5f}'})", file=sys.stderr)
        output = runner.run({"spring": {"name": name or "", "latitude": latitude, "longitude": longitude, "elevation_m": elevation_m},
                             "field": field})
        return tool_summary(output)

    return [find_spring_in_dataset, assess_vulnerability]


def request_params(effort):
    return {"model": MODEL, "max_tokens": MAX_TOKENS, "system": SYSTEM_PROMPT, "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort}, "betas": [FALLBACK_BETA], "fallbacks": "default"}


def run_turn(client, tools, messages, user_text, effort):
    """Run one user turn through the tool runner; extend `messages` with the turn's user, assistant and tool messages."""
    start = len(messages)
    messages.append({"role": "user", "content": user_text})
    runner = client.beta.messages.tool_runner(tools=tools, messages=messages, max_iterations=MAX_TOOL_ROUNDS, **request_params(effort))
    last = None
    for message in runner:
        last = message
        messages.append({"role": "assistant", "content": message.to_param()["content"]})
        tool_response = runner.generate_tool_call_response()  # cached, so each tool still runs once
        if tool_response is not None:
            messages.append(tool_response)
    if last is None or last.stop_reason == "refusal":
        del messages[start:]  # a refused or empty turn is not kept in the conversation
        return "The model declined to answer that. Try rephrasing the question." if last else "(no answer came back)"
    text = "\n".join(b.text for b in last.content if b.type == "text").strip()
    if last.stop_reason == "max_tokens":
        text += "\n(The answer was cut off at the length limit.)"
    return text or "(no text in the answer)"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ask", help="Ask one question and exit")
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"],
                        help="How hard the model thinks (default high)")
    parser.add_argument("--cache", default=os.environ.get("SPRING_LAYER_CACHE", str(ROOT / ".layer_cache")))
    parser.add_argument("--local-layers", default=os.environ.get("SPRING_LOCAL_LAYERS", str(ROOT / ".local_layers")))
    args = parser.parse_args()

    import anthropic
    client = anthropic.Anthropic()
    tools = make_tools(ModuleARunner(args.cache, args.local_layers))
    messages = []
    if args.ask:
        print(run_turn(client, tools, messages, args.ask, args.effort))
        return
    print("Spring vulnerability assistant. Describe a spring, or type quit to stop.")
    while True:
        try:
            text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in ("quit", "exit", "q"):
            break
        if not text:
            continue
        print("\nAssistant: " + run_turn(client, tools, messages, text, args.effort))


if __name__ == "__main__":
    main()

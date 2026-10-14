"""Module A checks: how much the result depends on the draft weights, and how well it matches known declines.

Sensitivity (runs now, on the input springs only; test springs are not used)
  python scripts/module_a_checks.py --sensitivity
  - Each indicator's weight is halved, raised by half, and dropped, one at a time: how many springs change class.
  - 1,000 random weight sets (every weight times 0.5-1.5): how often each spring keeps its class.
  - The Low/Medium/High cut-offs moved by 5 points.
  - The decline weight at 15 / 20 / 25 for each answer to "flow now vs 10-20 years ago" (a what-if: the dataset has
    no such answers, so every hill spring is given the same answer in turn).
  Writes data/03_outputs/module_a/sensitivity_v1.txt and sensitivity_by_indicator_v1.csv.

Validation (run once, when the field-visit answers or WATSAN's list of declining / steady springs come in)
  python scripts/module_a_checks.py --validate my_springs.csv [--cache ... --local-layers ...]
  - The file follows config/module_a_validation_template.csv: one spring per row, with record_id (dataset springs)
    or latitude / longitude / elevation_m (new springs), the known outcome (decline_label: declining / steady /
    unsure, or the flow_vs_past answer), and any other field answers.
  - Each spring is scored WITHOUT its flow_vs_past answer, because that answer is the outcome being predicted.
  - Reports how well the score separates declining from steady springs (AUC), the class table, and each spring.
  - Many of these springs sit in the held-out test set. Every run is logged in validation_log.csv, so a repeat
    look at the same springs is visible: tune weights before this check, not after.
"""

import argparse
import csv
import hashlib
import math
import random
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import module_a_vulnerability as A  # noqa: E402

OUT = A.OUT_DIR
DRAWS = 1000
SEED = 20261014
STEPS = {"halved": 0.5, "raised by half": 1.5, "dropped": 0.0}
CUT_SHIFT = 5
DECLINE_WEIGHTS = (15, 20, 25)
DECLINING = {"much_less", "dries_at_times"}
STEADY = {"more", "same"}


def classify(score, cuts=A.CLASS_CUTS):
    return "Low" if score < cuts[0] else "Medium" if score < cuts[1] else "High"


def weighted(scores, weights):
    """Weighted mean of the indicators a spring has, as score_spring does."""
    used = sum(weights[k] for k in scores)
    return sum(s * weights[k] for k, s in scores.items()) / used if used else None


def dataset_springs():
    """Indicator scores (0-100) for each input spring, from the dataset (map values + WATSAN flows and seasonality)."""
    indicators = A.load_indicators()
    reference, features = A.load_reference()
    master = {r["record_id"]: r for r in A.read_csv(A.INPUT_CSV)}
    springs = []
    for f in features:
        if f["coordinate_status"] != "ok":
            continue
        m = master[f["record_id"]]
        answers, _ = A.clean_answers({"lean_flow_lpm": m["discharge_dry_lpm"], "monsoon_flow_lpm": m["discharge_monsoon_lpm"],
                                      "seasonality": A.parse_seasonality(m["seasonality_text"]) or ""})
        elevation = A._num(f, "dem_elevation_m")
        result = A.score_spring(f, answers, indicators, reference, elevation)
        if result["items"]:
            springs.append({"record_id": f["record_id"], "hill": elevation is None or elevation >= A.HILL_MIN_ELEVATION_M,
                            "scores": {i["id"]: i["score"] for i in result["items"]}})
    return springs, indicators


# --------------------------------------------------------------------------- sensitivity
def sensitivity():
    springs, indicators = dataset_springs()
    base_w = {k: m["weight"] for k, m in indicators.items()}
    base = [classify(weighted(s["scores"], base_w)) for s in springs]
    n = len(springs)
    lines = [f"Module A sensitivity to the draft weights ({datetime.now():%Y-%m-%d})",
             f"Input springs with at least one scored indicator: {n} (test springs not used).",
             "The dataset has no field answers except WATSAN's flow estimates and seasonality labels, so this mostly tests",
             "the map indicators. The last section shows the decline question as a what-if.", "",
             "Baseline classes: " + ", ".join(f"{c} {base.count(c)}" for c in ("Low", "Medium", "High")), ""]

    rows = []
    for key, meta in indicators.items():
        have = sum(1 for s in springs if key in s["scores"])
        if not have:
            continue
        row = {"id": key, "indicator": meta["indicator"], "weight": meta["weight"], "springs_with_value": have}
        for label, factor in STEPS.items():
            w = dict(base_w, **{key: base_w[key] * factor})
            changed = sum(1 for s, b in zip(springs, base) if (sc := weighted(s["scores"], w)) is not None and classify(sc) != b)
            row[f"pct_changing_class_if_{label.replace(' ', '_')}"] = round(100 * changed / n, 1)
        rows.append(row)
    rows.sort(key=lambda r: -r["pct_changing_class_if_dropped"])
    with (OUT / "sensitivity_by_indicator_v1.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    lines.append("1. One weight at a time: % of springs that change class")
    lines.append(f"   {'indicator':45} weight  halved  +50%  dropped")
    for r in rows:
        lines.append(f"   {r['indicator'][:45]:45} {r['weight']:>5.0f}  {r['pct_changing_class_if_halved']:>6.1f}  "
                     f"{r['pct_changing_class_if_raised_by_half']:>4.1f}  {r['pct_changing_class_if_dropped']:>7.1f}")

    rng = random.Random(SEED)
    same = [0] * n
    for _ in range(DRAWS):
        w = {k: v * rng.uniform(0.5, 1.5) for k, v in base_w.items()}
        for i, s in enumerate(springs):
            same[i] += classify(weighted(s["scores"], w)) == base[i]
    share = [c / DRAWS for c in same]
    lines += ["", f"2. {DRAWS} random weight sets (each weight times 0.5-1.5): how often a spring keeps its class",
              f"   Same class in at least 90% of sets: {100 * sum(x >= 0.9 for x in share) / n:.0f}% of springs",
              f"   Same class in at least 75% of sets: {100 * sum(x >= 0.75 for x in share) / n:.0f}% of springs",
              f"   Same class in under half the sets:  {100 * sum(x < 0.5 for x in share) / n:.0f}% of springs (these sit near a cut-off)"]

    scores = [weighted(s["scores"], base_w) for s in springs]
    lines += ["", f"3. Cut-offs moved by {CUT_SHIFT} points (baseline Low < {A.CLASS_CUTS[0]}, High >= {A.CLASS_CUTS[1]})"]
    for shift in (-CUT_SHIFT, CUT_SHIFT):
        cuts = (A.CLASS_CUTS[0] + shift, A.CLASS_CUTS[1] + shift)
        moved = [classify(sc, cuts) for sc in scores]
        lines.append(f"   Cut-offs {cuts[0]} / {cuts[1]}: {100 * sum(a != b for a, b in zip(moved, base)) / n:.0f}% change class; "
                     + ", ".join(f"{c} {moved.count(c)}" for c in ("Low", "Medium", "High")))

    hills = [s for s in springs if s["hill"]]
    lines += ["", f"4. What-if: every hill spring ({len(hills)}) gives the same answer to 'flow now vs 10-20 years ago'",
              "   Share of springs in each class (Low / Medium / High), by the weight of the decline question:",
              "   answer            " + "".join(f"weight {d:<14}" for d in DECLINE_WEIGHTS)]
    for answer, points in (("same or more", 0), ("a bit less", 50), ("much less / dries", 100)):
        cells = []
        for d in DECLINE_WEIGHTS:
            w = dict(base_w, flow_vs_past=d)
            classes = []
            for s in hills:
                sc = weighted(dict(s["scores"], flow_vs_past=points), w)
                c = classify(sc)
                classes.append("Medium" if points == 100 and c == "Low" else c)  # floor rule
            cells.append("/".join(f"{100 * classes.count(c) / len(classes):.0f}" for c in ("Low", "Medium", "High")))
        lines.append(f"   {answer:18}" + "".join(f"{c:<21}" for c in cells))
    text = "\n".join(lines)
    (OUT / "sensitivity_v1.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


# --------------------------------------------------------------------------- validation
def outcome(row):
    """declining / steady / None from decline_label, else from the flow_vs_past answer. Second value: a_bit_less."""
    label = (row.get("decline_label") or "").strip().lower()
    if label in ("declining", "steady"):
        return label, False
    answers, _ = A.clean_answers({"flow_vs_past": row.get("flow_vs_past", "")})
    trend = answers.get("flow_vs_past")
    if trend in DECLINING:
        return "declining", False
    if trend in STEADY:
        return "steady", False
    if trend == "a_bit_less":
        return "declining", True
    return None, False


def auc(declining, steady):
    """Chance that a declining spring scores higher than a steady one (ties count half)."""
    wins = sum((d > s) + 0.5 * (d == s) for d in declining for s in steady)
    return wins / (len(declining) * len(steady))


def validate(path, cache, local_layers):
    indicators = A.load_indicators()
    reference, _ = A.load_reference()
    features_by_id = {f["record_id"]: f for f in A.read_csv(A.FEATURES_CSV)}
    session = None
    results, skipped = [], []
    for row in A.read_csv(Path(path)):
        name = row.get("name") or row.get("record_id") or f"{row.get('latitude')}, {row.get('longitude')}"
        label, slight = outcome(row)
        if label is None:
            skipped.append(f"{name}: no decline_label or flow_vs_past answer")
            continue
        raw = {k: row.get(k, "") for k in A.OPTIONAL if k != "flow_vs_past"}
        answers, problems = A.clean_answers(raw)
        f = features_by_id.get((row.get("record_id") or "").strip())
        if f is not None:
            f = {k: v for k, v in f.items() if v not in ("", None)}
            elevation = float(row["elevation_m"]) if row.get("elevation_m") else A._num(f, "dem_elevation_m")
        elif row.get("latitude") and row.get("longitude") and row.get("elevation_m"):
            if session is None:
                session = A.LayerSession(cache, local_layers)
            elevation = float(row["elevation_m"])
            f = session.features(float(row["latitude"]), float(row["longitude"]), elevation)
        else:
            skipped.append(f"{name}: needs a dataset record_id, or latitude, longitude and elevation_m")
            continue
        r = A.score_spring(f, answers, indicators, reference, elevation)
        results.append({"name": name, "record_id": row.get("record_id", ""), "outcome": label, "a_bit_less": slight,
                         "label_source": row.get("label_source", ""), "score": round(r["score"], 1), "class": r["class"],
                         "coverage_pct": round(r["coverage_pct"]), "problems": "; ".join(problems)})

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    lines = [f"Module A validation, {stamp}: {path}",
             "Each spring is scored without its flow_vs_past answer, which is the outcome being checked.", ""]
    for title, keep in (("Strict: much less or dries vs same or more", lambda r: not r["a_bit_less"]),
                        ("Broad: any less (including a bit less) vs same or more", lambda r: True)):
        sub = [r for r in results if keep(r)]
        dec = [r["score"] for r in sub if r["outcome"] == "declining"]
        std = [r["score"] for r in sub if r["outcome"] == "steady"]
        lines.append(f"{title}: {len(dec)} declining, {len(std)} steady")
        if dec and std:
            lines.append(f"  Median score: declining {statistics.median(dec):.0f}, steady {statistics.median(std):.0f}")
            lines.append(f"  AUC {auc(dec, std):.2f} (0.5 = no better than chance, 1.0 = every declining spring scores above every steady one)")
            if min(len(dec), len(std)) < 10:
                lines.append("  Fewer than 10 springs in a group: treat this as an indication, not a result.")
        lines.append("  Class      declining  steady")
        for c in ("Low", "Medium", "High"):
            lines.append(f"  {c:9} {sum(r['class'] == c for r in sub if r['outcome'] == 'declining'):>9}  "
                         f"{sum(r['class'] == c for r in sub if r['outcome'] == 'steady'):>6}")
        lines.append("")
    if skipped:
        lines += ["Skipped:"] + [f"  {s}" for s in skipped]

    log_path = OUT / "validation_log.csv"
    ids = sorted(r["record_id"] or r["name"] for r in results)
    key = hashlib.sha1("|".join(ids).encode()).hexdigest()[:12]
    weights_key = hashlib.sha1(A.INDICATORS_CSV.read_bytes()).hexdigest()[:12]
    earlier = [r for r in A.read_csv(log_path) if r["springs_key"] == key] if log_path.exists() else []
    if earlier:
        lines.insert(1, f"NOTE: these same springs were checked before ({', '.join(r['run'] for r in earlier)}). "
                        "If weights changed in between, this is no longer an independent check.")
    new_log = not log_path.exists()
    with log_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        if new_log:
            writer.writerow(["run", "file", "springs", "springs_key", "weights_key"])
        writer.writerow([stamp, str(path), len(results), key, weights_key])

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / f"validation_{stamp}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]) if results else ["name"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)
    text = "\n".join(lines)
    (OUT / f"validation_{stamp}.txt").write_text(text + "\n", encoding="utf-8")
    print(text)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sensitivity", action="store_true")
    parser.add_argument("--validate", metavar="CSV")
    parser.add_argument("--cache", default=str(ROOT / ".layer_cache"))
    parser.add_argument("--local-layers", default=str(ROOT / ".local_layers"))
    args = parser.parse_args()
    if args.sensitivity:
        sensitivity()
    elif args.validate:
        validate(args.validate, args.cache, args.local_layers)
    else:
        parser.error("give --sensitivity or --validate FILE")


if __name__ == "__main__":
    main()

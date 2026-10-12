"""Decide which colocated records (within 30 m) are the same spring.

Each pair of records in a colocated group gets one decision:
- same:      a confirmed link (team decision file, or a profile matched to its Atlas annexure row
             during transcription), or the names match and the source elevations agree within 60 m.
- different: source elevations differ by more than 100 m, the same base name carries different
             position words (Talla / Malla / Bichla, I / II, 1 / 2), or both names are specific and clearly different.
             These are separate springs that share a coordinate (often a coordinate copied in the source).
- review:    anything else, usually a generic name ("Naula", "Dhara", "road") next to a named spring,
             or names that are only partly alike. A person who knows the villages decides these.
Records joined by "same" pairs form one spring. A record whose only links are "review" pairs stays a
separate spring, sharing no values, until the team decides.

Team decisions go in data/01_staged/common/duplicate_review_decisions_v1.csv (one row per pair:
record_id_a, record_id_b, decision = same or different, decided_by, decided_on, note). They override
the rules on the next build.
"""

import csv
import re
from difflib import SequenceMatcher

SAME_ELEVATION_M = 60
DIFFERENT_ELEVATION_M = 100
NAME_MATCH = 0.75
NAME_DIFFERENT = 0.5

GENERIC = {"naula", "naulas", "dhara", "dharas", "spring", "springs", "source", "gadhera", "gadera", "srot", "chashma",
           "ka", "ki", "ke", "the", "of", "near"}
POSITION = {"talla": "talla", "tall": "talla", "tallo": "talla", "malla": "malla", "mall": "malla", "mallo": "malla",
            "bichla": "bichla", "bichli": "bichla", "upper": "malla", "lower": "talla",
            "i": "1", "1": "1", "ii": "2", "2": "2", "iii": "3", "3": "3"}


def _tokens(text):
    return [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if t]


def _core(name):
    """Specific part of a spring name: no generic words, no position words."""
    return "".join(t for t in _tokens(name) if t not in GENERIC and t not in POSITION)


def _position(name):
    return {POSITION[t] for t in _tokens(name) if t in POSITION}


def _similar(a, b):
    if not a or not b:
        return None
    if len(a) >= 4 and len(b) >= 4 and (a in b or b in a):
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def load_decisions(path):
    decisions = {}
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                decision = row["decision"].strip().lower()
                if decision in ("same", "different"):
                    key = frozenset((row["record_id_a"].strip(), row["record_id_b"].strip()))
                    decisions[key] = (decision, f"team decision ({row.get('decided_by', '').strip() or 'unnamed'}, {row.get('decided_on', '').strip()})")
    return decisions


def pair_decision(a, b, links, decisions):
    """a, b: dicts with record_id, spring_name, village, elevation_source_m. Returns (decision, reason)."""
    key = frozenset((a["record_id"], b["record_id"]))
    if key in decisions:
        return decisions[key]
    if key in links:
        return "same", "matched during transcription (Atlas profile to its annexure row)"
    ea, eb = a["elevation_source_m"], b["elevation_source_m"]
    gap = abs(float(ea) - float(eb)) if ea and eb else None
    if gap is not None and gap > DIFFERENT_ELEVATION_M:
        return "different", f"source elevations differ by {gap:.0f} m"
    pa, pb = _position(a["spring_name"]), _position(b["spring_name"])
    ca, cb = _core(a["spring_name"]), _core(b["spring_name"])
    # Talla vs Malla, or "Kholiya Naula" vs "Kholiya Naula 2": the same base name in different positions
    if pa != pb and ((pa and pb) or (ca and ca == cb)):
        return "different", f"different position in the name ({'/'.join(sorted(pa)) or 'none'} vs {'/'.join(sorted(pb)) or 'none'})"
    name_sim = _similar(ca, cb)
    village_sim = _similar(_core(a["village"]), _core(b["village"]))
    if name_sim is None and ca == cb == "":
        name_sim = village_sim  # both names generic: the village is all there is to compare
    elev_ok = gap is None or gap <= SAME_ELEVATION_M
    if name_sim is not None and name_sim >= NAME_MATCH and elev_ok:
        return "same", "names match" + (f", elevations within {gap:.0f} m" if gap is not None else "")
    if name_sim is not None and name_sim < NAME_DIFFERENT and ca and cb:
        return "different", "different spring names sharing a coordinate"
    ta = {t for t in _tokens(a["spring_name"]) if t not in GENERIC and t not in POSITION}
    tb = {t for t in _tokens(b["spring_name"]) if t not in GENERIC and t not in POSITION}
    if len(ta) > 1 and len(tb) > 1 and ta & tb and ta - tb and tb - ta:
        return "different", f"same first name, different qualifier ({', '.join(sorted(ta - tb))} vs {', '.join(sorted(tb - ta))})"
    if not ca or not cb:
        return "review", "one name is generic; cannot tell from the records"
    return "review", "names only partly alike"


def resolve_group(members, links, decisions):
    """Return (pairs, clusters, status). clusters: list of lists of record ids that are one spring."""
    pairs = []
    parent = {m["record_id"]: m["record_id"] for m in members}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    for i, a in enumerate(members):
        for b in members[i + 1:]:
            decision, reason = pair_decision(a, b, links, decisions)
            pairs.append((a["record_id"], b["record_id"], decision, reason))
    for a, b, decision, _ in pairs:
        if decision == "same":
            parent[find(a)] = find(b)
    clusters = {}
    for m in members:
        clusters.setdefault(find(m["record_id"]), []).append(m["record_id"])
    clusters = list(clusters.values())
    # A "different" pair inside one merged cluster contradicts itself: send it to review.
    for a, b, decision, _ in pairs:
        if decision == "different" and find(a) == find(b):
            return pairs, [[m["record_id"]] for m in members], "needs review"
    if any(d == "review" for *_, d, _ in pairs):
        status = "needs review"
    elif len(clusters) == 1:
        status = "same spring"
    elif len(clusters) == len(members):
        status = "different springs"
    else:
        status = "partly the same spring"
    return pairs, clusters, status

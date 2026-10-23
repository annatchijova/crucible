"""Check adjudication responses and report proportions, assigning no labels.

A proportion is only meaningful if the denominator is honest, so this reports
per stratum and never pools, and it keeps CENSUS strata separate from SAMPLE
strata: a census proportion is exact over its population, a sample proportion
is an estimate this frame cannot attach an interval to.

Like the coverage response validator, it refuses a submission that is not
bound to the frame it claims, carries an outcome outside the allowed set,
omits a rationale, or claims an authenticated reviewer identity that no trust
root supports.

Usage:
    python validate_adjudication.py <frame.json> <response.json> [<response-b.json>]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from crucible.ir import digest_payload

FRAME_VERSION = "adjudication-frame/v1"
RESPONSE_VERSION = "adjudication-response/v1"
OUTCOMES = ("CONFIRMED", "REJECTED", "UNRESOLVED")

POOLING_LIMITATION = (
    "proportions are reported per stratum and never pooled: the strata differ "
    "in population by two orders of magnitude, so a pooled figure would be "
    "dominated by whichever class the auditor happens to emit most"
)


def fail(message: str) -> None:
    raise SystemExit(f"error: {message}")


def load_frame(path: Path) -> tuple[dict, dict]:
    frame = json.loads(path.read_text(encoding="utf-8"))
    if frame.get("schema_version") != FRAME_VERSION:
        fail(f"{path.name}: unsupported frame schema")
    if frame.get("annotation_state") != "UNLABELED":
        fail(f"{path.name}: the frame itself must carry no labels")
    sealed = {k: v for k, v in frame.items() if k != "frame_digest"}
    if frame.get("frame_digest") != digest_payload(sealed):
        fail(f"{path.name}: frame digest mismatch")
    index = {}
    for stratum in frame["strata"]:
        for item in stratum["selection"]:
            index[item["selector"]] = (stratum["corpus_id"],
                                       stratum["finding_class"],
                                       stratum["coverage"],
                                       stratum["population"])
    return frame, index


def validate(path: Path, frame: dict, index: dict) -> dict:
    response = json.loads(path.read_text(encoding="utf-8"))
    if response.get("schema_version") != RESPONSE_VERSION:
        fail(f"{path.name}: unsupported response schema")
    if response.get("frame_digest") != frame["frame_digest"]:
        fail(f"{path.name}: response is not bound to this frame digest")
    label = response.get("reviewer_label")
    if not isinstance(label, str) or not label.strip():
        fail(f"{path.name}: reviewer_label is required")
    if response.get("authenticity_status") != "UNVERIFIED":
        fail(f"{path.name}: no reviewer trust root exists; status must stay UNVERIFIED")
    assessments = response.get("assessments")
    if not isinstance(assessments, list):
        fail(f"{path.name}: assessments must be a list")
    expected = [item["selector"] for s in frame["strata"] for item in s["selection"]]
    if [a.get("selector") for a in assessments] != expected:
        fail(f"{path.name}: assessments do not match the frame selection order")

    answered = {}
    for item in assessments:
        outcome = item.get("outcome")
        if outcome is None:
            continue
        if outcome not in OUTCOMES:
            fail(f"{path.name}: {item['selector']}: outcome {outcome!r} is not allowed")
        if not isinstance(item.get("rationale"), str) or not item["rationale"].strip():
            fail(f"{path.name}: {item['selector']}: a rationale is required")
        if outcome != "UNRESOLVED" and not item.get("source_quote"):
            fail(f"{path.name}: {item['selector']}: {outcome} must quote the source it rests on")
        answered[item["selector"]] = outcome
    return {"reviewer_label": label, "file": path.name, "answered": answered}


def proportions(review: dict, index: dict) -> list[dict]:
    """Per-stratum counts. A stratum is reported only once a reviewer touched it."""
    buckets: dict[tuple, dict] = {}
    for selector, outcome in review["answered"].items():
        corpus_id, finding_class, coverage, population = index[selector]
        key = (corpus_id, finding_class)
        bucket = buckets.setdefault(key, {
            "corpus_id": corpus_id, "finding_class": finding_class,
            "coverage": coverage, "population": population, "adjudicated": 0,
            **{outcome_name: 0 for outcome_name in OUTCOMES},
        })
        bucket["adjudicated"] += 1
        bucket[outcome] += 1
    report = []
    for key in sorted(buckets):
        bucket = buckets[key]
        decided = bucket["CONFIRMED"] + bucket["REJECTED"]
        # A ratio, not a float: n/d keeps the denominator visible and avoids
        # putting a rounded decimal where an exact count belongs.
        bucket["confirmed_of_decided"] = (
            f"{bucket['CONFIRMED']}/{decided}" if decided else "0/0"
        )
        bucket["claim"] = (
            "exact over this stratum" if bucket["coverage"] == "CENSUS"
            else "estimate; no interval available from this frame"
        )
        report.append(bucket)
    return report


def main() -> None:
    if not 3 <= len(sys.argv) <= 4:
        raise SystemExit(__doc__)
    frame, index = load_frame(Path(sys.argv[1]))
    reviews = [validate(Path(arg), frame, index) for arg in sys.argv[2:]]
    if len(reviews) == 2 and reviews[0]["reviewer_label"] == reviews[1]["reviewer_label"]:
        fail("both responses carry the same reviewer_label")
    report = {
        "frame_digest": frame["frame_digest"],
        "pooling_limitation": POOLING_LIMITATION,
        "frame_limitation": frame["limitation"],
        "reviews": [{
            "reviewer_label": review["reviewer_label"],
            "file": review["file"],
            "answered_count": len(review["answered"]),
            "selected_total": frame["selected_total"],
            "strata": proportions(review, index),
        } for review in reviews],
    }
    if len(reviews) == 2:
        shared = sorted(set(reviews[0]["answered"]) & set(reviews[1]["answered"]))
        disagree = [{
            "selector": s,
            "corpus_id": index[s][0],
            "finding_class": index[s][1],
            reviews[0]["reviewer_label"]: reviews[0]["answered"][s],
            reviews[1]["reviewer_label"]: reviews[1]["answered"][s],
            "disposition": "UNRESOLVED pending a separately recorded third review",
        } for s in shared if reviews[0]["answered"][s] != reviews[1]["answered"][s]]
        report["comparison"] = {
            "compared": len(shared),
            "agreed": len(shared) - len(disagree),
            "disagreed": len(disagree),
            "disagreements": disagree,
            "limitation": "agreement between reviewers is not evidence that "
                          "either is correct; no kappa or interval is computed",
        }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

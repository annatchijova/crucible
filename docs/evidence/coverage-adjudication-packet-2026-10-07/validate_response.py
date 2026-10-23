"""Check submitted reviewer responses and report agreement, assigning no labels.

`validate_packet.py` checks that the packet can be handed out. This checks what
comes back: that a response is bound to the packet it claims, that every
outcome is one the rubric allows, that quotes were copied from the packet
rather than paraphrased, and that PARTIAL and UNRESOLVED carry the extra
information PROTOCOL.md requires for them.

It computes agreement counts and lists disagreements. It deliberately computes
no accuracy, no kappa and no confidence interval: there is no answer key, the
19 pairs are correlated within 16 cases, and PROTOCOL.md step 5 forbids corpus
estimates from this set. Agreement between two reviewers is not evidence that
either is right.

Usage:
    python validate_response.py <response.json> [<response-b.json>]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from crucible.ir import digest_payload

ROOT = Path(__file__).resolve().parent
OUTCOMES = ("COVERS", "PARTIAL", "DOES_NOT_COVER", "UNRESOLVED")
RESPONSE_SCHEMA = "coverage-adjudication-response/v1"
PACKET_SCHEMA = "coverage-adjudication-packet/v1"
RUBRIC = "coverage-text/v1"


def load_packet() -> tuple[dict, str, dict[str, str], list[str], dict[str, str]]:
    packet = json.loads((ROOT / "packet.json").read_text(encoding="utf-8"))
    pair_order: list[str] = []
    pair_phase: dict[str, str] = {}
    pair_source: dict[str, str] = {}
    for phase in ("calibration", "heldout"):
        for case in packet[phase]:
            for pair in case["pairs"]:
                pair_order.append(pair["pair_id"])
                pair_phase[pair["pair_id"]] = phase
                pair_source[pair["pair_id"]] = case["source_text"]
    return packet, digest_payload(packet), pair_phase, pair_order, pair_source


def fail(message: str) -> None:
    raise SystemExit(f"error: {message}")


def validate(path: Path, digest: str, pair_order: list[str],
             pair_phase: dict[str, str], pair_source: dict[str, str]) -> dict:
    response = json.loads(path.read_text(encoding="utf-8"))
    label = response.get("reviewer_label")
    if response.get("schema_version") != RESPONSE_SCHEMA:
        fail(f"{path.name}: unsupported response schema")
    if response.get("packet_schema_version") != PACKET_SCHEMA:
        fail(f"{path.name}: unsupported packet schema")
    if response.get("rubric_version") != RUBRIC:
        fail(f"{path.name}: unsupported rubric version")
    if response.get("packet_digest") != digest:
        fail(f"{path.name}: response is not bound to this packet digest")
    if not isinstance(label, str) or not label.strip():
        fail(f"{path.name}: reviewer_label is required")
    if response.get("authenticity_status") != "UNVERIFIED":
        fail(f"{path.name}: no reviewer trust root exists; status must stay UNVERIFIED")

    assessments = response.get("assessments")
    if not isinstance(assessments, list):
        fail(f"{path.name}: assessments must be a list")
    if [item.get("pair_id") for item in assessments] != pair_order:
        fail(f"{path.name}: assessments do not match the packet pair order")

    answered: dict[str, str] = {}
    blank: list[str] = []
    for item in assessments:
        pair_id = item["pair_id"]
        outcome = item.get("outcome")
        if outcome is None:
            blank.append(pair_id)
            continue
        if outcome not in OUTCOMES:
            fail(f"{path.name}: {pair_id}: outcome {outcome!r} is not in the rubric")
        rationale = item.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            fail(f"{path.name}: {pair_id}: a rationale is required for every judgement")
        quotes = item.get("evidence_quotes")
        if not isinstance(quotes, list) or not quotes:
            fail(f"{path.name}: {pair_id}: at least one evidence quote is required")
        for quote in quotes:
            if not isinstance(quote, str) or quote.strip() not in pair_source[pair_id]:
                fail(f"{path.name}: {pair_id}: quote is not copied from the packet: "
                     f"{str(quote)[:60]!r}")
        clauses = item.get("covered_rule_clauses")
        if not isinstance(clauses, list):
            fail(f"{path.name}: {pair_id}: covered_rule_clauses must be a list")
        if outcome == "PARTIAL" and not clauses:
            fail(f"{path.name}: {pair_id}: PARTIAL must name the covered clauses")
        if outcome in ("COVERS", "PARTIAL") and not item.get("oracle"):
            fail(f"{path.name}: {pair_id}: {outcome} must name the oracle")
        if outcome == "DOES_NOT_COVER" and clauses:
            fail(f"{path.name}: {pair_id}: DOES_NOT_COVER cannot list covered clauses")
        answered[pair_id] = outcome

    phases_complete = sorted({
        phase for phase in ("calibration", "heldout")
        if all(pair_phase[p] != phase or p in answered for p in pair_order)
        and any(pair_phase[p] == phase for p in answered)
    })
    return {
        "reviewer_label": label,
        "file": path.name,
        "answered": answered,
        "blank_pairs": blank,
        "phases_complete": phases_complete,
        "authenticity_status": "UNVERIFIED",
    }


def compare(first: dict, second: dict, pair_phase: dict[str, str]) -> dict:
    shared = sorted(set(first["answered"]) & set(second["answered"]))
    agree = [p for p in shared if first["answered"][p] == second["answered"][p]]
    disagree = [
        {"pair_id": p, "phase": pair_phase[p],
         first["reviewer_label"]: first["answered"][p],
         second["reviewer_label"]: second["answered"][p],
         "disposition": "UNRESOLVED pending a separately recorded third review"}
        for p in shared if first["answered"][p] != second["answered"][p]
    ]
    return {
        "compared_pairs": len(shared),
        "agreed": len(agree),
        "disagreed": len(disagree),
        "only_one_reviewer_answered": sorted(
            set(first["answered"]) ^ set(second["answered"])
        ),
        "disagreements": disagree,
        "limitation": (
            "agreement is not accuracy: this packet has no answer key, the "
            "pairs are correlated within cases, and no kappa, interval or "
            "corpus estimate may be computed from it"
        ),
    }


def main() -> None:
    if not 2 <= len(sys.argv) <= 3:
        raise SystemExit(__doc__)
    packet, digest, pair_phase, pair_order, pair_source = load_packet()
    reviews = [
        validate(Path(arg), digest, pair_order, pair_phase, pair_source)
        for arg in sys.argv[1:]
    ]
    report = {
        "packet_digest": digest,
        "rubric_version": RUBRIC,
        "reviews": [
            {k: v for k, v in review.items() if k != "answered"} | {
                "answered_count": len(review["answered"]),
                "outcome_counts": {
                    outcome: sum(1 for o in review["answered"].values() if o == outcome)
                    for outcome in OUTCOMES
                    if any(o == outcome for o in review["answered"].values())
                },
            }
            for review in reviews
        ],
    }
    if len(reviews) == 2:
        if reviews[0]["reviewer_label"] == reviews[1]["reviewer_label"]:
            fail("both responses carry the same reviewer_label")
        report["comparison"] = compare(reviews[0], reviews[1], pair_phase)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

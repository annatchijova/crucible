"""Check packet integrity without assigning or guessing relation labels."""

from __future__ import annotations

import json
from pathlib import Path

from crucible.ir import digest_payload


ROOT = Path(__file__).resolve().parent
FORBIDDEN_LABEL_KEYS = {
    "expected",
    "expected_link",
    "gold",
    "gold_label",
    "label",
    "outcome",
    "prediction",
    "score",
}


def _walk(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def main() -> None:
    packet = json.loads((ROOT / "packet.json").read_text(encoding="utf-8"))
    response = json.loads(
        (ROOT / "response-template.json").read_text(encoding="utf-8")
    )
    if packet.get("schema_version") != "coverage-adjudication-packet/v1":
        raise SystemExit("unsupported packet schema")
    if packet.get("rubric_version") != "coverage-text/v1":
        raise SystemExit("unsupported rubric version")
    if packet.get("annotation_state") != "UNLABELED":
        raise SystemExit("packet must remain unlabeled")
    if set(_walk(packet)) & FORBIDDEN_LABEL_KEYS:
        raise SystemExit("packet includes an answer or prediction field")

    all_case_ids: set[str] = set()
    all_pair_ids: list[str] = []
    phase_counts: dict[str, dict[str, int]] = {}
    for phase in ("calibration", "heldout"):
        cases = packet.get(phase)
        if not isinstance(cases, list) or not cases:
            raise SystemExit(f"{phase} must be a non-empty list")
        pair_count = 0
        for case in cases:
            case_id = case.get("case_id")
            if not isinstance(case_id, str) or case_id in all_case_ids:
                raise SystemExit("case IDs must be unique strings")
            all_case_ids.add(case_id)
            rules, checks, pairs = case.get("rules"), case.get("checks"), case.get("pairs")
            if not isinstance(rules, list) or not rules or not isinstance(checks, list) or not checks:
                raise SystemExit(f"{case_id}: rules/checks must be non-empty lists")
            expected = {
                (rule["id"], check["id"])
                for rule in rules
                for check in checks
            }
            observed: set[tuple[str, str]] = set()
            for pair in pairs:
                key = (pair.get("rule_id"), pair.get("check_id"))
                if key in observed:
                    raise SystemExit(f"{case_id}: duplicate pair {key!r}")
                if pair.get("pair_id") != f"{case_id}/{key[0]}/{key[1]}":
                    raise SystemExit(f"{case_id}: pair ID does not bind its relation")
                observed.add(key)
                all_pair_ids.append(pair["pair_id"])
            if observed != expected:
                raise SystemExit(f"{case_id}: pair list is not the full rule/check product")
            for item in [*rules, *checks]:
                if item["text"] not in case["source_text"]:
                    raise SystemExit(f"{case_id}: item text is absent from source context")
            pair_count += len(pairs)
        phase_counts[phase] = {"cases": len(cases), "pairs": pair_count}

    template_ids = [item.get("pair_id") for item in response.get("assessments", [])]
    if template_ids != all_pair_ids:
        raise SystemExit("response template does not match packet pair order")
    if response.get("authenticity_status") != "UNVERIFIED":
        raise SystemExit("template must not claim authenticated reviewer identity")
    packet_digest = digest_payload(packet)
    if response.get("packet_digest") != packet_digest:
        raise SystemExit("response template is not bound to this packet digest")

    print(json.dumps({
        "packet_digest": packet_digest,
        "case_count": len(all_case_ids),
        "pair_count": len(all_pair_ids),
        "phases": phase_counts,
        "answer_labels_present": False,
        "template_matches_pairs": True,
        "reviewer_authentication": "UNVERIFIED",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

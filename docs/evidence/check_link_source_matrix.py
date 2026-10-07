"""Offline, synthetic comparison of rule-to-check link evidence sources.

This is an experiment harness, not production code. It compiles small Markdown
fixtures with the current L1 compiler, then compares source-declared links and
the existing deterministic Jaccard primitive against author-stated fixture
labels. Ambiguous cases are reported but excluded from the small metrics.

Run from the repository root with:
    .venv/bin/python docs/evidence/check_link_source_matrix.py
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from crucible.auditor import _jaccard, _tokenize
from crucible.compiler import compile_corpus


CASES: list[dict[str, Any]] = [
    {
        "name": "clear_related",
        "body": (
            "The request MUST be idempotent.\n\n"
            "## Checks\n\n"
            "- Verify that the request is idempotent by submitting it twice "
            "and comparing state.\n"
        ),
        "expected_links": [[0, 0]],
        "declared_links": [[0, 0]],
    },
    {
        "name": "incorrect_author_declaration",
        "body": (
            "The request MUST be idempotent.\n\n"
            "## Checks\n\n"
            "- Verify the detached signature matches the publisher key.\n"
        ),
        "expected_links": [],
        # Deliberately wrong: metadata can faithfully preserve a false claim.
        "declared_links": [[0, 0]],
    },
    {
        "name": "partial_generic_overlap",
        "body": (
            "The request MUST be authenticated.\n"
            "The request MUST be idempotent.\n\n"
            "## Checks\n\n"
            "- Verify the request signature against the publisher key.\n"
        ),
        "expected_links": [[0, 0]],
        "declared_links": [[0, 0]],
    },
    {
        "name": "workflow_only",
        "body": (
            "Requests MUST be reviewed against an approved policy.\n\n"
            "## Live Odds Check\n\n"
            "1. Search markets for the requested event.\n"
        ),
        "expected_links": [],
        "declared_links": [],
    },
    {
        "name": "direct_condition_without_verb",
        "body": (
            "The response status MUST be exactly 200.\n\n"
            "## Validation Criteria\n\n"
            "- The response status is exactly 200.\n"
        ),
        "expected_links": [[0, 0]],
        "declared_links": [],
    },
    {
        "name": "ambiguous_policy_review",
        "body": (
            "Requests MUST be handled in accordance with approved policy.\n\n"
            "## Checks\n\n"
            "- Review the request against the approved policy.\n"
        ),
        # Human label is intentionally unresolved; do not tune on this case.
        "expected_links": None,
        "declared_links": [],
    },
]


def _ratio(numerator: int, denominator: int) -> str | None:
    if denominator == 0:
        return None
    return f"{numerator}/{denominator}"


def _metrics(
    predicted: set[tuple[str, str, str]],
    expected: set[tuple[str, str, str]],
) -> dict[str, Any]:
    true_positive = len(predicted & expected)
    false_positive = len(predicted - expected)
    false_negative = len(expected - predicted)
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": _ratio(true_positive, true_positive + false_positive),
        "recall": _ratio(true_positive, true_positive + false_negative),
    }


def main() -> None:
    compiled: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="crucible-check-link-matrix-") as temp:
        root = Path(temp)
        for case in CASES:
            skill_dir = root / case["name"]
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                f"name: {case['name']}\n"
                "description: Synthetic check-link experiment fixture.\n"
                "---\n\n"
                + case["body"],
                encoding="utf-8",
                newline="\n",
            )
        artifact = compile_corpus(root)
        by_name = {
            skill["identity"]["name"]: skill for skill in artifact["skills"]
        }

        for case in CASES:
            skill = by_name[case["name"]]
            rules = skill["rules"]
            checks = skill["checks"]
            scores: list[dict[str, str]] = []
            for rule_index, rule in enumerate(rules):
                for check_index, check in enumerate(checks):
                    overlap = _jaccard(
                        _tokenize(rule["text"]), _tokenize(check["text"])
                    )
                    scores.append({
                        "rule_id": rule["id"],
                        "check_id": check["id"],
                        "jaccard": f"{overlap.numerator}/{overlap.denominator}",
                        "oracle_kind": check["oracle_kind"],
                    })
            compiled.append({
                **case,
                "rules": rules,
                "checks": checks,
                "scores": scores,
            })

    labeled_cases = [case for case in compiled if case["expected_links"] is not None]
    expected_edges: set[tuple[str, str, str]] = set()
    declared_edges: set[tuple[str, str, str]] = set()
    all_pair_edges: set[tuple[str, str, str]] = set()
    for case in labeled_cases:
        name = case["name"]
        for rule_index, check_index in case["expected_links"]:
            expected_edges.add((name, case["rules"][rule_index]["id"],
                                case["checks"][check_index]["id"]))
        for rule_index, check_index in case["declared_links"]:
            declared_edges.add((name, case["rules"][rule_index]["id"],
                                case["checks"][check_index]["id"]))
        for rule in case["rules"]:
            for check in case["checks"]:
                all_pair_edges.add((name, rule["id"], check["id"]))

    jaccard_predictions: dict[str, set[tuple[str, str, str]]] = {}
    # These are comparison points, not fitted or calibrated thresholds.
    # 1/7 comes from the previously inspected partial fixture; 1/5 is a
    # contrast point. This fixture set is therefore not an independent test.
    for threshold in (Fraction(1, 7), Fraction(1, 5)):
        predicted: set[tuple[str, str, str]] = set()
        for case in labeled_cases:
            name = case["name"]
            for score in case["scores"]:
                n, d = score["jaccard"].split("/")
                if Fraction(int(n), int(d)) >= threshold:
                    predicted.add((name, score["rule_id"], score["check_id"]))
        jaccard_predictions[str(threshold)] = predicted

    output = {
        "experiment": "rule-check-link-source-matrix/v1",
        "scope": "synthetic, author-labeled fixtures; not a corpus estimate",
        "compiled_ir_digest": artifact["artifact_digest"],
        "labeled_case_count": len(labeled_cases),
        "ambiguous_case_count": len(compiled) - len(labeled_cases),
        "expected_edge_count": len(expected_edges),
        "metrics": {
            "no_links": _metrics(set(), expected_edges),
            "all_pairs": _metrics(all_pair_edges, expected_edges),
            "author_declarations": _metrics(declared_edges, expected_edges),
            **{
                f"jaccard_at_least_{threshold}": _metrics(predicted, expected_edges)
                for threshold, predicted in jaccard_predictions.items()
            },
        },
        "cases": [
            {
                "name": case["name"],
                "label_status": (
                    "ABSTAIN" if case["expected_links"] is None else "LABELED"
                ),
                "rule_ids": [rule["id"] for rule in case["rules"]],
                "check_ids": [check["id"] for check in case["checks"]],
                "expected_links": (
                    None if case["expected_links"] is None else [
                        {
                            "rule_id": case["rules"][rule_index]["id"],
                            "check_id": case["checks"][check_index]["id"],
                        }
                        for rule_index, check_index in case["expected_links"]
                    ]
                ),
                "declared_links": [
                    {
                        "rule_id": case["rules"][rule_index]["id"],
                        "check_id": case["checks"][check_index]["id"],
                    }
                    for rule_index, check_index in case["declared_links"]
                ],
                "scores": case["scores"],
            }
            for case in compiled
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

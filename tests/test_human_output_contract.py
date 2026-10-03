"""Falsifiable contract tests for human_output.py (--human CLI rendering).

format_human never computes anything the underlying report didn't
already contain; these tests check it renders the right content for
each recognized report shape and falls back to JSON for anything else.
"""

from __future__ import annotations

import json

from crucible.human_output import format_human


# ---------------------------------------------------------------------------
# Dispatch by shape
# ---------------------------------------------------------------------------

def test_audit_artifact_lists_each_finding() -> None:
    """Invariant: every finding's class, skill, and evidence appear in
    the rendered text. Mutation: drop a finding from the loop -> red."""
    report = {
        "audit_digest": "sha256:abc",
        "findings": [
            {"class": "UNBOUNDED_RETRY", "skill": "retry-a",
             "epistemic_status": "CANDIDATE", "evidence": "no bound found"},
        ],
        "limitations": [],
    }
    out = format_human(report)
    assert "UNBOUNDED_RETRY" in out
    assert "retry-a" in out
    assert "no bound found" in out
    assert "sha256:abc" in out


def test_mutation_report_shows_kill_rate_and_survivor_classification() -> None:
    """Invariant: kill rate and each mutation's status/survivor
    classification are rendered. Mutation: omit survivor_classification
    for a SURVIVED mutant -> red (loses diagnostic information)."""
    report = {
        "mutation_digest": "sha256:xyz",
        "summary": {"kill_rate": "5/6"},
        "results": [
            {"mutation_id": "M001-x", "status": "SURVIVED",
             "survivor_classification": "INSUFFICIENT_DETECTOR"},
            {"mutation_id": "M002-y", "status": "KILLED",
             "survivor_classification": None},
        ],
    }
    out = format_human(report)
    assert "5/6" in out
    assert "M001-x" in out and "INSUFFICIENT_DETECTOR" in out
    assert "M002-y" in out and "KILLED" in out


def test_behavioral_report_shows_variant_and_property_evidence() -> None:
    """Invariant: each variant's status and each property's real
    evidence string are rendered (this is the activation-trace surface).
    Mutation: show only status, not evidence -> red."""
    report = {
        "behavioral_digest": "sha256:beh",
        "nebius_blocked": False,
        "runs": [
            {"variant_id": "V2-original", "status": "COMPLETED",
             "observations": [
                 {"property_id": "P1-mentions-budget", "status": "PASS",
                  "evidence": "keyword_present: matched 'finite' in \"...\""},
             ]},
        ],
    }
    out = format_human(report)
    assert "V2-original" in out
    assert "P1-mentions-budget" in out
    assert "matched 'finite'" in out


def test_graph_artifact_shows_edges_and_properties() -> None:
    """Invariant: edges (with resolution status) and graph properties are
    rendered. Mutation: hide unresolved edges -> red."""
    report = {
        "graph_digest": "sha256:g",
        "nodes": [{"name": "a"}],
        "edges": [
            {"source": "a", "target": "ghost", "edge_type": "COMPOSES_WITH",
             "symmetric": False, "resolved": False},
        ],
        "graph_properties": [
            {"property": "BROKEN_EDGE", "skill": "a", "evidence": "target not found"},
        ],
    }
    out = format_human(report)
    assert "a -> ghost" in out
    assert "unresolved" in out
    assert "BROKEN_EDGE" in out


def test_confirmation_artifact_shows_verdict_and_rationale() -> None:
    """Invariant: each confirmation's verdict, class, and rationale are
    rendered, and a BLOCKED status is surfaced explicitly.
    Mutation: silently drop BLOCKED status -> red."""
    report = {
        "confirmation_digest": "sha256:c",
        "status": "BLOCKED",
        "summary": {"confirmed": 0, "rejected": 0, "unclear": 1},
        "confirmations": [
            {"finding_id": "finding-0001", "finding_class": "SEMANTIC_REDUNDANCY",
             "verdict": "UNCLEAR", "rationale": "no credential"},
        ],
    }
    out = format_human(report)
    assert "BLOCKED" in out
    assert "SEMANTIC_REDUNDANCY" in out
    assert "no credential" in out


def test_single_outcome_report_shows_rejection_reason_and_gaps() -> None:
    """Invariant: a REJECTED outcome's reason and gap counts are shown.
    Mutation: omit rejection_reason -> red (loses why it failed)."""
    report = {
        "consolidation_version": "crucible-consolidation/v1",
        "outcome": "REJECTED",
        "rejection_reason": "COVERAGE_GAP",
        "cluster": ["retry-a", "retry-b"],
        "proposal": {"proposed_name": "retry-merged", "rationale": "merged"},
        "coverage_gaps": [{"source_skill": "retry-a", "item_type": "check"}],
        "new_findings": [],
        "external_references": [],
        "rewritten_external_references": [],
    }
    out = format_human(report)
    assert "REJECTED" in out
    assert "COVERAGE_GAP" in out
    assert "retry-a, retry-b" in out
    assert "coverage_gaps: 1 item(s)" in out


def test_consolidation_batch_shows_per_cluster_outcomes() -> None:
    """Invariant: the batch summary counts and each cluster's own outcome
    are both rendered. Mutation: only show the summary, not per-cluster
    outcomes -> red."""
    report = {
        "batch_digest": "sha256:b",
        "batch_status": "COMPLETED",
        "total_clusters": 2,
        "accepted_count": 1,
        "rejected_count": 1,
        "blocked_count": 0,
        "reports": [
            {"cluster": ["a", "b"], "outcome": "ACCEPTED"},
            {"cluster": ["c", "d"], "outcome": "REJECTED"},
        ],
        "final_skill_names": ["merged-ab", "c", "d"],
    }
    out = format_human(report)
    assert "COMPLETED" in out
    assert "['a', 'b']" in out and "ACCEPTED" in out
    assert "['c', 'd']" in out and "REJECTED" in out
    assert "merged-ab" in out


# ---------------------------------------------------------------------------
# Fallback and safety
# ---------------------------------------------------------------------------

def test_unrecognized_shape_falls_back_to_json() -> None:
    """Invariant: a dict with no recognized signature key renders as the
    same pretty JSON the non-human path would print -- --human is never
    a downgrade. Mutation: raise or print nothing for unknown shapes -> red."""
    report = {"some_unknown_report_type": True, "value": 42}
    out = format_human(report)
    assert json.loads(out) == report


def test_non_dict_input_does_not_crash() -> None:
    """Invariant: a non-dict report (e.g. a bare list) is handled without
    raising. Mutation: assume input is always a dict -> red (AttributeError)."""
    out = format_human([1, 2, 3])
    assert "1" in out


def test_color_codes_are_absent_without_a_tty() -> None:
    """Invariant: under pytest (no real terminal attached to stdout),
    no ANSI escape codes are emitted -- piped/redirected output must stay
    plain text. Mutation: emit color unconditionally -> red."""
    report = {
        "audit_digest": "sha256:abc",
        "findings": [{"class": "X", "skill": "y", "epistemic_status": "CONFIRMED", "evidence": "e"}],
        "limitations": [],
    }
    out = format_human(report)
    assert "\x1b[" not in out

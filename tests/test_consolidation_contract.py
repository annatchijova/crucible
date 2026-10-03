"""Falsifiable contract tests for the L16 skill consolidation workflow.

Each test names the invariant it defends and the mutation that would catch
a regression, mirroring tests/test_repair_loop_contract.py's style.
"""

from __future__ import annotations

from crucible.consolidation import (
    BATCH_STATUS_COMPLETED,
    BATCH_STATUS_NO_CLUSTERS,
    CONSOLIDATION_FIXTURE,
    OUTCOME_NO_CLUSTERS,
    _compile_ir_and_audit,
    find_redundancy_clusters,
    run_consolidation,
    run_consolidation_batch,
)
from crucible.bob import OUTCOME_ACCEPTED, OUTCOME_BLOCKED, OUTCOME_REJECTED


class NaiveConcatProposer:
    """Test fixture only -- not a real engineering proposer.

    Concatenating skill texts is not consolidation: it does not dedupe,
    rename sensibly, or produce idiomatic SKILL.md structure. It exists
    solely to exercise the deterministic acceptance gate with a
    predictable, dependency-free proposal. Never wire this into the CLI.
    """

    def __init__(self, name: str = "retry-merged", drop_check: bool = False) -> None:
        self.name = name
        self.drop_check = drop_check

    def propose_merge(self, cluster_skills, evidence, context):
        checks_section = (
            ""
            if self.drop_check
            else (
                "\n## Checks\n\n"
                "- Verify the retry budget is enforced: "
                "run `scripts/check_budget.sh`.\n"
            )
        )
        text = (
            f"---\nname: {self.name}\n"
            "description: Retry failed network calls and requests with a bounded budget.\n"
            "license: Apache-2.0\n---\n\n"
            "# Retry network operations\n\n"
            "Retries MUST have a finite budget.\n"
            f"{checks_section}"
        )
        return {
            "proposed_name": self.name,
            "proposed_text": text,
            "rationale": "concatenated test double",
            "proposer": "naive-concat-test-only",
        }


class GenericMergeProposer:
    """Test fixture only -- see NaiveConcatProposer's docstring.

    Unlike NaiveConcatProposer, this one is domain-agnostic: it renames
    the first cluster member and keeps its rules/checks verbatim, so it
    works for any cluster, not just a hardcoded retry-budget skill. Used
    for batch tests that process more than one cluster at once.
    """

    def __init__(self, fail_for_prefix: str | None = None) -> None:
        self.fail_for_prefix = fail_for_prefix

    def propose_merge(self, cluster_skills, evidence, context):
        first_name = cluster_skills[0]["name"]
        merged_name = f"{first_name}-merged"
        text = cluster_skills[0]["text"].replace(
            f"name: {first_name}", f"name: {merged_name}", 1
        )
        if self.fail_for_prefix and first_name.startswith(self.fail_for_prefix):
            # Drop the Checks section entirely -> coverage gap.
            text = text.split("## Checks")[0]
        return {
            "proposed_name": merged_name,
            "proposed_text": text,
            "rationale": "generic test merge",
            "proposer": "generic-merge-test-only",
        }


TWO_CLUSTER_FIXTURE = {
    "retry-a": (
        "---\nname: retry-a\n"
        "description: Retry network calls with a bounded budget.\n"
        "license: Apache-2.0\n---\n\n# Retry\n\n"
        "Retries MUST have a finite budget.\n\n"
        "## Checks\n\n- Verify the retry budget: run `scripts/check_budget.sh`.\n"
    ),
    "retry-b": (
        "---\nname: retry-b\n"
        "description: Retry network calls with a bounded budget.\n"
        "license: Apache-2.0\n---\n\n# Retry\n\n"
        "Retries MUST have a finite budget.\n\n"
        "## Checks\n\n- Verify the retry budget: run `scripts/check_budget.sh`.\n"
    ),
    "format-a": (
        "---\nname: format-a\n"
        "description: Format currency values for display.\n"
        "license: Apache-2.0\n---\n\n# Format\n\n"
        "Amounts MUST have two decimals.\n\n"
        "## Checks\n\n- Verify the format: run `scripts/check_format.sh`.\n"
    ),
    "format-b": (
        "---\nname: format-b\n"
        "description: Format currency values for display.\n"
        "license: Apache-2.0\n---\n\n# Format\n\n"
        "Amounts MUST have two decimals.\n\n"
        "## Checks\n\n- Verify the format: run `scripts/check_format.sh`.\n"
    ),
}


def _confirm_all_semantic_redundancy(audit):
    return {
        "confirmations": [
            {"finding_id": f["id"], "verdict": "CONFIRMED"}
            for f in audit["findings"]
            if f["class"] == "SEMANTIC_REDUNDANCY"
        ]
    }


class BlockedProposer:
    def propose_merge(self, cluster_skills, evidence, context):
        return {
            "proposed_name": None,
            "proposed_text": None,
            "rationale": "NEBIUS_API_KEY not set",
            "proposer": "llm-nebius-consolidation",
            "blocked": True,
        }


def _confirmed(audit, cls="SEMANTIC_REDUNDANCY"):
    finding = next(f for f in audit["findings"] if f["class"] == cls)
    return {"confirmations": [{"finding_id": finding["id"], "verdict": "CONFIRMED"}]}


def _candidate_only(audit, cls="SEMANTIC_REDUNDANCY"):
    finding = next(f for f in audit["findings"] if f["class"] == cls)
    return {"confirmations": [{"finding_id": finding["id"], "verdict": "REJECTED"}]}


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def test_confirmed_duplicates_form_one_cluster() -> None:
    """Invariant: two CONFIRMED-redundant skills form one cluster.
    Mutation: break the _find_components call -> red."""
    ir, audit = _compile_ir_and_audit(CONSOLIDATION_FIXTURE)
    confirmation = _confirmed(audit)
    clusters = find_redundancy_clusters(audit, confirmation)
    assert clusters == [["retry-a", "retry-b"]]


def test_unconfirmed_pair_does_not_cluster() -> None:
    """Invariant: a CANDIDATE finding with a REJECTED (or absent) verdict
    does not form a cluster -- CANDIDATE alone is never enough.
    Mutation: key off epistemic_status instead of the confirmation
    verdict -> red."""
    ir, audit = _compile_ir_and_audit(CONSOLIDATION_FIXTURE)
    confirmation = _candidate_only(audit)
    clusters = find_redundancy_clusters(audit, confirmation)
    assert clusters == []


def test_no_confirmation_means_no_clusters() -> None:
    """Invariant: without a confirmation artifact at all, there are no
    clusters -- an unconfirmed CANDIDATE must never silently drive a
    merge. Mutation: cluster on raw CANDIDATE findings -> red."""
    report = run_consolidation(corpus=CONSOLIDATION_FIXTURE, confirmation=None)
    assert report["outcome"] == OUTCOME_NO_CLUSTERS


# ---------------------------------------------------------------------------
# External reference precondition
# ---------------------------------------------------------------------------

def test_external_reference_blocks_merge() -> None:
    """Invariant: a skill outside the cluster referencing a cluster member
    by name blocks the whole merge.
    Mutation: skip the precondition check -> red (would silently merge and
    break external-caller's reference)."""
    corpus = dict(CONSOLIDATION_FIXTURE)
    corpus["external-caller"] = (
        "---\nname: external-caller\n"
        "description: Calls into the retry skill.\n"
        "license: Apache-2.0\n---\n\n"
        "# External caller\n\n"
        "Calls MUST be bounded.\n\n"
        "## Composes with\n\n- retry-a\n"
    )
    ir, audit = _compile_ir_and_audit(corpus)
    confirmation = _confirmed(audit)
    report = run_consolidation(
        corpus=corpus, confirmation=confirmation, proposer=NaiveConcatProposer()
    )
    assert report["outcome"] == OUTCOME_REJECTED
    assert report["rejection_reason"] == "EXTERNAL_REFERENCE_BLOCK"
    assert len(report["external_references"]) == 1
    assert report["external_references"][0]["source"] == "external-caller"
    assert report["external_references"][0]["target"] == "retry-a"
    # No proposal should even be attempted once blocked.
    assert report["proposal"] is None


# ---------------------------------------------------------------------------
# Coverage gate
# ---------------------------------------------------------------------------

def test_coverage_gap_rejects_merge() -> None:
    """Invariant: a merge that drops an original check is rejected with
    COVERAGE_GAP naming the missing text.
    Mutation: only check redundancy-gone, not coverage -> red."""
    ir, audit = _compile_ir_and_audit(CONSOLIDATION_FIXTURE)
    confirmation = _confirmed(audit)
    report = run_consolidation(
        corpus=CONSOLIDATION_FIXTURE, confirmation=confirmation,
        proposer=NaiveConcatProposer(drop_check=True),
    )
    assert report["outcome"] == OUTCOME_REJECTED
    assert report["rejection_reason"] == "COVERAGE_GAP"
    assert len(report["coverage_gaps"]) == 2  # one per original skill's check
    assert all(g["item_type"] == "check" for g in report["coverage_gaps"])


# ---------------------------------------------------------------------------
# Acceptance
# ---------------------------------------------------------------------------

def test_good_merge_is_accepted() -> None:
    """Invariant: a complete merge covering both originals' rules and
    checks is ACCEPTED, with the redundancy resolved and no new findings.
    Mutation: skip the novelty or coverage check -> red (would accept an
    incomplete or regressive merge)."""
    ir, audit = _compile_ir_and_audit(CONSOLIDATION_FIXTURE)
    confirmation = _confirmed(audit)
    report = run_consolidation(
        corpus=CONSOLIDATION_FIXTURE, confirmation=confirmation,
        proposer=NaiveConcatProposer(),
    )
    assert report["outcome"] == OUTCOME_ACCEPTED
    assert report["rejection_reason"] is None
    assert report["redundancy_resolved"] is True
    assert report["coverage_gaps"] == []
    assert report["new_findings"] == []
    assert report["cluster"] == ["retry-a", "retry-b"]
    assert report["consolidation_digest"].startswith("sha256:")
    # Explicit, not omitted: no behavioral claim is made.
    assert report["behavioral_gate"] is None
    assert report["determinism_level"] == "deterministic_text_only"


def test_no_proposal_is_blocked() -> None:
    """Invariant: a proposer that cannot produce a proposal (e.g. no API
    key) yields BLOCKED, not a silent accept or reject.
    Mutation: treat blocked the same as rejected -> red."""
    ir, audit = _compile_ir_and_audit(CONSOLIDATION_FIXTURE)
    confirmation = _confirmed(audit)
    report = run_consolidation(
        corpus=CONSOLIDATION_FIXTURE, confirmation=confirmation,
        proposer=BlockedProposer(),
    )
    assert report["outcome"] == OUTCOME_BLOCKED
    assert report["rejection_reason"] is None


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_is_deterministic() -> None:
    """Invariant: two runs on the same input produce the same digest.
    Mutation: introduce non-determinism -> red."""
    ir, audit = _compile_ir_and_audit(CONSOLIDATION_FIXTURE)
    confirmation = _confirmed(audit)
    r1 = run_consolidation(
        corpus=CONSOLIDATION_FIXTURE, confirmation=confirmation,
        proposer=NaiveConcatProposer(),
    )
    r2 = run_consolidation(
        corpus=CONSOLIDATION_FIXTURE, confirmation=confirmation,
        proposer=NaiveConcatProposer(),
    )
    assert r1["consolidation_digest"] == r2["consolidation_digest"]
    assert r1["outcome"] == r2["outcome"] == OUTCOME_ACCEPTED


# ---------------------------------------------------------------------------
# Batch mode
# ---------------------------------------------------------------------------

def test_batch_processes_two_independent_clusters() -> None:
    """Invariant: two unrelated redundancy clusters are both found and
    both merged in one batch call.
    Mutation: only process clusters[0] -> red (would silently ignore the
    second cluster)."""
    ir, audit = _compile_ir_and_audit(TWO_CLUSTER_FIXTURE)
    confirmation = _confirm_all_semantic_redundancy(audit)
    batch = run_consolidation_batch(
        corpus=TWO_CLUSTER_FIXTURE, confirmation=confirmation,
        proposer=GenericMergeProposer(),
    )
    assert batch["batch_status"] == BATCH_STATUS_COMPLETED
    assert batch["total_clusters"] == 2
    assert batch["accepted_count"] == 2
    assert batch["rejected_count"] == 0
    assert set(batch["final_skill_names"]) == {"retry-a-merged", "format-a-merged"}


def test_batch_continues_after_one_cluster_rejected() -> None:
    """Invariant: a rejected cluster does not block the rest of the
    batch -- this is a batch of independent attempts, not a transaction.
    Mutation: abort the whole batch on the first rejection -> red."""
    ir, audit = _compile_ir_and_audit(TWO_CLUSTER_FIXTURE)
    confirmation = _confirm_all_semantic_redundancy(audit)
    batch = run_consolidation_batch(
        corpus=TWO_CLUSTER_FIXTURE, confirmation=confirmation,
        proposer=GenericMergeProposer(fail_for_prefix="retry"),
    )
    assert batch["batch_status"] == BATCH_STATUS_COMPLETED
    assert batch["accepted_count"] == 1
    assert batch["rejected_count"] == 1
    outcomes_by_cluster = {
        tuple(sorted(r["cluster"])): r["outcome"] for r in batch["reports"]
    }
    assert outcomes_by_cluster[("retry-a", "retry-b")] == OUTCOME_REJECTED
    assert outcomes_by_cluster[("format-a", "format-b")] == OUTCOME_ACCEPTED
    # The rejected cluster's members stay in the corpus, unmerged.
    assert "retry-a" in batch["final_skill_names"]
    assert "retry-b" in batch["final_skill_names"]
    assert "format-a-merged" in batch["final_skill_names"]


def test_batch_no_clusters_reports_status() -> None:
    """Invariant: with no confirmed redundancy, the batch reports
    NO_CLUSTERS and an empty report list, not an error.
    Mutation: raise instead of returning a status -> red."""
    batch = run_consolidation_batch(
        corpus=CONSOLIDATION_FIXTURE, confirmation=None,
    )
    assert batch["batch_status"] == BATCH_STATUS_NO_CLUSTERS
    assert batch["total_clusters"] == 0
    assert batch["reports"] == []


def test_batch_is_deterministic() -> None:
    """Invariant: two batch runs on the same input produce the same
    digest. Mutation: introduce non-determinism -> red."""
    ir, audit = _compile_ir_and_audit(TWO_CLUSTER_FIXTURE)
    confirmation = _confirm_all_semantic_redundancy(audit)
    b1 = run_consolidation_batch(
        corpus=TWO_CLUSTER_FIXTURE, confirmation=confirmation,
        proposer=GenericMergeProposer(),
    )
    b2 = run_consolidation_batch(
        corpus=TWO_CLUSTER_FIXTURE, confirmation=confirmation,
        proposer=GenericMergeProposer(),
    )
    assert b1["batch_digest"] == b2["batch_digest"]

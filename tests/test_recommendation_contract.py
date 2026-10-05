"""Contract tests for the L15 deterministic recommendation core."""

from crucible.recommendation import compute_recommendations


def _finding(id_, cls, skill, epistemic_status="CANDIDATE"):
    return {
        "id": id_,
        "class": cls,
        "epistemic_status": epistemic_status,
        "skill": skill,
        "evidence": "evidence",
    }


def _confirmation(audit_digest, entries):
    return {
        "confirmation_digest": "sha256:conf",
        "source_audit_digest": audit_digest,
        "confirmations": [
            {"finding_id": fid, "verdict": verdict} for fid, verdict in entries
        ],
    }


def test_without_all_skill_names_a_clean_skill_has_no_entry_at_all():
    """Documents the limitation, not the desired behavior: without
    ``all_skill_names``, a skill with zero findings is invisible to this
    function entirely -- not even a KEEP entry, since the only skill
    names it can see come from ``audit["findings"]``. See
    ``test_clean_skill_gets_an_explicit_keep_entry`` for the fix."""
    audit = {"audit_digest": "sha256:a", "findings": []}
    result = compute_recommendations(audit)
    assert result["skills"] == {}
    assert result["schema_version"] == "crucible-recommendation/v1"


def test_clean_skill_gets_an_explicit_keep_entry() -> None:
    """Invariant: a skill with zero findings gets an explicit KEEP entry
    when the full corpus skill list is known -- not silent omission.
    Confirmed as a real bug otherwise: `build_final_report`'s rendered
    report states the true skill_count in its header but the body lists
    nothing for a clean skill, a visible, misleading gap.
    Mutation: drop the all_skill_names merge -> this test goes red."""
    audit = {
        "audit_digest": "sha256:a",
        "findings": [_finding("f1", "REQUIREMENT_WITHOUT_CHECK", "bad-skill")],
    }
    result = compute_recommendations(audit, all_skill_names=["bad-skill", "clean-skill"])
    assert result["skills"]["clean-skill"]["recommendation"] == "KEEP"
    assert result["skills"]["clean-skill"]["total_finding_count"] == 0
    assert result["skills"]["bad-skill"]["recommendation"] == "NEEDS_CONFIRMATION"


def test_unconfirmed_candidate_needs_confirmation_not_action():
    audit = {
        "audit_digest": "sha256:a",
        "findings": [_finding("f1", "REQUIREMENT_WITHOUT_CHECK", "retrier")],
    }
    result = compute_recommendations(audit)
    assert result["skills"]["retrier"]["recommendation"] == "NEEDS_CONFIRMATION"
    assert result["skills"]["retrier"]["pending_finding_ids"] == ["f1"]
    assert result["skills"]["retrier"]["confirmed_finding_ids"] == []


def test_l2_native_confirmed_finding_recommends_modify():
    audit = {
        "audit_digest": "sha256:a",
        "findings": [_finding("f1", "SELF_COMPOSITION", "looper", epistemic_status="CONFIRMED")],
    }
    result = compute_recommendations(audit)
    assert result["skills"]["looper"]["recommendation"] == "MODIFY"
    assert result["skills"]["looper"]["confirmed_finding_ids"] == ["f1"]


def test_l25_confirmed_candidate_recommends_modify():
    audit = {
        "audit_digest": "sha256:a",
        "findings": [_finding("f1", "UNBOUNDED_RETRY", "retrier")],
    }
    confirmation = _confirmation("sha256:a", [("f1", "CONFIRMED")])
    result = compute_recommendations(audit, confirmation)
    assert result["skills"]["retrier"]["recommendation"] == "MODIFY"
    assert result["skills"]["retrier"]["confirmed_finding_ids"] == ["f1"]
    assert result["skills"]["retrier"]["pending_finding_ids"] == []


def test_rejected_candidate_is_excluded_and_skill_is_kept():
    audit = {
        "audit_digest": "sha256:a",
        "findings": [_finding("f1", "REQUIREMENT_WITHOUT_CHECK", "retrier")],
    }
    confirmation = _confirmation("sha256:a", [("f1", "REJECTED")])
    result = compute_recommendations(audit, confirmation)
    assert result["skills"]["retrier"]["recommendation"] == "KEEP"
    assert result["skills"]["retrier"]["rejected_finding_ids"] == ["f1"]
    assert result["skills"]["retrier"]["confirmed_finding_ids"] == []


def test_confirmed_redundancy_recommends_delete_over_modify():
    audit = {
        "audit_digest": "sha256:a",
        "findings": [
            _finding("f1", "SEMANTIC_REDUNDANCY", "dup-skill"),
            _finding("f2", "UNBOUNDED_RETRY", "dup-skill"),
        ],
    }
    confirmation = _confirmation("sha256:a", [("f1", "CONFIRMED"), ("f2", "CONFIRMED")])
    result = compute_recommendations(audit, confirmation)
    assert result["skills"]["dup-skill"]["recommendation"] == "DELETE"
    assert set(result["skills"]["dup-skill"]["confirmed_finding_ids"]) == {"f1", "f2"}


def test_unclear_verdict_is_treated_as_pending_not_confirmed():
    audit = {
        "audit_digest": "sha256:a",
        "findings": [_finding("f1", "REQUIREMENT_WITHOUT_CHECK", "retrier")],
    }
    confirmation = _confirmation("sha256:a", [("f1", "UNCLEAR")])
    result = compute_recommendations(audit, confirmation)
    assert result["skills"]["retrier"]["recommendation"] == "NEEDS_CONFIRMATION"
    assert result["skills"]["retrier"]["pending_finding_ids"] == ["f1"]


def test_confirmation_from_a_different_audit_is_not_trusted():
    audit = {
        "audit_digest": "sha256:current",
        "findings": [_finding("f1", "REQUIREMENT_WITHOUT_CHECK", "retrier")],
    }
    # This confirmation was computed against a stale/different audit digest.
    confirmation = _confirmation("sha256:stale", [("f1", "CONFIRMED")])
    result = compute_recommendations(audit, confirmation)
    assert result["confirmation_digest_mismatch"] is True
    # The mismatched confirmation's CONFIRMED verdict must not be trusted;
    # the CANDIDATE finding falls back to needing confirmation.
    assert result["skills"]["retrier"]["recommendation"] == "NEEDS_CONFIRMATION"
    assert result["skills"]["retrier"]["confirmed_finding_ids"] == []


def test_corpus_level_finding_with_no_skill_gets_a_bucket():
    audit = {
        "audit_digest": "sha256:a",
        "findings": [_finding("f1", "ORPHAN_SKILL", None, epistemic_status="CONFIRMED")],
    }
    result = compute_recommendations(audit)
    assert "(corpus-level)" in result["skills"]
    assert result["skills"]["(corpus-level)"]["recommendation"] == "MODIFY"


def test_deterministic_digest_is_stable_across_key_ordering():
    audit_a = {
        "audit_digest": "sha256:a",
        "findings": [_finding("f1", "UNBOUNDED_RETRY", "b-skill"), _finding("f2", "UNBOUNDED_RETRY", "a-skill")],
    }
    audit_b = {
        "findings": list(reversed(audit_a["findings"])),
        "audit_digest": "sha256:a",
    }
    result_a = compute_recommendations(audit_a)
    result_b = compute_recommendations(audit_b)
    assert result_a["recommendation_digest"] == result_b["recommendation_digest"]


def test_multi_skill_corpus_gets_independent_recommendations():
    audit = {
        "audit_digest": "sha256:a",
        "findings": [
            _finding("f1", "SELF_COMPOSITION", "broken-skill", epistemic_status="CONFIRMED"),
            _finding("f2", "REQUIREMENT_WITHOUT_CHECK", "clean-skill"),
        ],
    }
    result = compute_recommendations(audit)
    assert result["skills"]["broken-skill"]["recommendation"] == "MODIFY"
    assert result["skills"]["clean-skill"]["recommendation"] == "NEEDS_CONFIRMATION"

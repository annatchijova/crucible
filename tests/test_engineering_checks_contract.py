"""Falsifiable contract tests for the six engineering/methodology checks.

Each test names the invariant it defends and the mutation it would catch.
Each check has a positive test (fires on the defect) and a negative test
(does not fire on a clean skill).
"""

from __future__ import annotations

from pathlib import Path

from crucible.auditor import audit_corpus
from crucible.compiler import compile_corpus


def _write_skill(root: Path, name: str, body: str) -> Path:
    skill = root / name
    skill.mkdir()
    (skill / "SKILL.md").write_text(body, encoding="utf-8", newline="\n")
    return skill


def _audit(root: Path) -> dict:
    return audit_corpus(compile_corpus(root))


def _classes(findings: list[dict]) -> list[str]:
    return sorted(f["class"] for f in findings)


# ---------------------------------------------------------------------------
# UNBOUNDED_RETRY
# ---------------------------------------------------------------------------

def test_unbounded_retry_fires_on_retry_without_bound(tmp_path: Path) -> None:
    """Invariant: a retry instruction must specify a bound.
    Mutation: remove the bound check -> this test goes red."""
    _write_skill(
        tmp_path,
        "retrier",
        "---\nname: retrier\ndescription: Retry operations.\n---\n\n"
        "Operations MUST retry until success.\n",
    )
    audit = _audit(tmp_path)
    assert "UNBOUNDED_RETRY" in _classes(audit["findings"])
    finding = next(f for f in audit["findings"] if f["class"] == "UNBOUNDED_RETRY")
    assert finding["epistemic_status"] == "CANDIDATE"


def test_unbounded_retry_does_not_fire_on_bounded_retry(tmp_path: Path) -> None:
    """Invariant: a bounded retry must not produce a false positive.
    Mutation: always emit UNBOUNDED_RETRY -> this test goes red."""
    _write_skill(
        tmp_path,
        "retrier",
        "---\nname: retrier\ndescription: Retry operations.\n---\n\n"
        "Operations MUST retry with a max of 3 attempts.\n",
    )
    audit = _audit(tmp_path)
    assert "UNBOUNDED_RETRY" not in _classes(audit["findings"])


def test_unbounded_retry_fires_on_step_without_bound(tmp_path: Path) -> None:
    """Invariant: a procedural step with retry must also be bounded.
    Mutation: only check rules, not steps -> this test goes red."""
    _write_skill(
        tmp_path,
        "retrier",
        "---\nname: retrier\ndescription: Retry operations.\n---\n\n"
        "Operations MUST be safe.\n\n"
        "## Steps\n\n"
        "1. Retry the operation until it succeeds.\n",
    )
    audit = _audit(tmp_path)
    assert "UNBOUNDED_RETRY" in _classes(audit["findings"])


def test_unbounded_retry_does_not_fire_on_backoff(tmp_path: Path) -> None:
    """Invariant: a backoff is a valid bound.
    Mutation: remove backoff from bound patterns -> this test goes red."""
    _write_skill(
        tmp_path,
        "retrier",
        "---\nname: retrier\ndescription: Retry operations.\n---\n\n"
        "Operations MUST retry with exponential backoff.\n",
    )
    audit = _audit(tmp_path)
    assert "UNBOUNDED_RETRY" not in _classes(audit["findings"])


# ---------------------------------------------------------------------------
# LLM_IN_DECISION_PATH
# ---------------------------------------------------------------------------

def test_llm_in_decision_path_fires_on_llm_verdict(tmp_path: Path) -> None:
    """Invariant: an LLM must not be the sole authority for a decision.
    Mutation: remove the LLM-decision check -> this test goes red."""
    _write_skill(
        tmp_path,
        "judge",
        "---\nname: judge\ndescription: Judge outputs.\n---\n\n"
        "The model MUST classify the output as safe or unsafe.\n",
    )
    audit = _audit(tmp_path)
    assert "LLM_IN_DECISION_PATH" in _classes(audit["findings"])
    finding = next(f for f in audit["findings"] if f["class"] == "LLM_IN_DECISION_PATH")
    assert finding["epistemic_status"] == "CANDIDATE"


def test_llm_in_decision_path_does_not_fire_with_guard(tmp_path: Path) -> None:
    """Invariant: a deterministic guard suppresses the finding.
    Mutation: remove the guard check -> this test goes red."""
    _write_skill(
        tmp_path,
        "judge",
        "---\nname: judge\ndescription: Judge outputs.\n---\n\n"
        "The model MUST classify the output, but a deterministic verifier MUST confirm.\n",
    )
    audit = _audit(tmp_path)
    assert "LLM_IN_DECISION_PATH" not in _classes(audit["findings"])


def test_llm_in_decision_path_fires_on_ask_model_to_decide(tmp_path: Path) -> None:
    """Invariant: 'ask the model to decide' is an LLM decision.
    Mutation: remove the 'ask the model' pattern -> this test goes red."""
    _write_skill(
        tmp_path,
        "judge",
        "---\nname: judge\ndescription: Judge outputs.\n---\n\n"
        "You MUST ask the model to evaluate the result.\n",
    )
    audit = _audit(tmp_path)
    assert "LLM_IN_DECISION_PATH" in _classes(audit["findings"])


# ---------------------------------------------------------------------------
# OVERCLAIM
# ---------------------------------------------------------------------------

def test_overclaim_fires_on_always(tmp_path: Path) -> None:
    """Invariant: 'always' without qualification is an overclaim.
    Mutation: remove 'always' from patterns -> this test goes red."""
    _write_skill(
        tmp_path,
        "absolute",
        "---\nname: absolute\ndescription: Absolute claims.\n---\n\n"
        "This method MUST always succeed.\n",
    )
    audit = _audit(tmp_path)
    assert "OVERCLAIM" in _classes(audit["findings"])
    finding = next(f for f in audit["findings"] if f["class"] == "OVERCLAIM")
    assert finding["epistemic_status"] == "CANDIDATE"


def test_overclaim_does_not_fire_on_qualified_claim(tmp_path: Path) -> None:
    """Invariant: a qualified claim is not an overclaim.
    Mutation: remove the qualification check -> this test goes red."""
    _write_skill(
        tmp_path,
        "qualified",
        "---\nname: qualified\ndescription: Qualified claims.\n---\n\n"
        "This method MUST typically succeed unless the input is malformed.\n",
    )
    audit = _audit(tmp_path)
    assert "OVERCLAIM" not in _classes(audit["findings"])


def test_overclaim_fires_on_guaranteed(tmp_path: Path) -> None:
    """Invariant: 'guaranteed' without qualification is an overclaim.
    Mutation: remove 'guaranteed' from patterns -> this test goes red."""
    _write_skill(
        tmp_path,
        "absolute",
        "---\nname: absolute\ndescription: Guaranteed claims.\n---\n\n"
        "The result MUST be guaranteed to be correct.\n",
    )
    audit = _audit(tmp_path)
    assert "OVERCLAIM" in _classes(audit["findings"])


# ---------------------------------------------------------------------------
# MISSING_FAILURE_MODE
# ---------------------------------------------------------------------------

def test_missing_failure_mode_fires_on_no_failure_mention(tmp_path: Path) -> None:
    """Invariant: a method with rules and steps must mention failure.
    Mutation: remove the failure-mode check -> this test goes red."""
    _write_skill(
        tmp_path,
        "happy",
        "---\nname: happy\ndescription: Happy path only.\n---\n\n"
        "Operations MUST be processed.\n\n"
        "## Steps\n\n"
        "1. Process the operation.\n"
        "2. Return the result.\n",
    )
    audit = _audit(tmp_path)
    assert "MISSING_FAILURE_MODE" in _classes(audit["findings"])
    finding = next(f for f in audit["findings"] if f["class"] == "MISSING_FAILURE_MODE")
    assert finding["epistemic_status"] == "CANDIDATE"


def test_missing_failure_mode_does_not_fire_with_error_handling(tmp_path: Path) -> None:
    """Invariant: a method that mentions failure is not missing a failure mode.
    Mutation: always emit MISSING_FAILURE_MODE -> this test goes red."""
    _write_skill(
        tmp_path,
        "safe",
        "---\nname: safe\ndescription: Safe method.\n---\n\n"
        "Operations MUST be processed.\n\n"
        "## Steps\n\n"
        "1. Process the operation.\n"
        "2. If the operation fails, report the error.\n",
    )
    audit = _audit(tmp_path)
    assert "MISSING_FAILURE_MODE" not in _classes(audit["findings"])


def test_missing_failure_mode_does_not_fire_without_steps(tmp_path: Path) -> None:
    """Invariant: a skill without steps is caught by METHODOLOGICAL_VACUITY,
    not MISSING_FAILURE_MODE.
    Mutation: fire MISSING_FAILURE_MODE without steps -> this test goes red."""
    _write_skill(
        tmp_path,
        "rules_only",
        "---\nname: rules_only\ndescription: Rules only.\n---\n\n"
        "Operations MUST be processed.\n",
    )
    audit = _audit(tmp_path)
    assert "MISSING_FAILURE_MODE" not in _classes(audit["findings"])


def test_missing_failure_mode_does_not_fire_on_conjugated_failure_word(
    tmp_path: Path,
) -> None:
    """Invariant: a conjugated form ('fails', not just 'fail'/'failed'/
    'failure') must still count as mentioning failure.
    Mutation: narrow the suffix alternation back to the original -> red.
    See docs/evidence/2026-10-02-missing-failure-mode-audit/FINDINGS.md,
    mechanism 1."""
    _write_skill(
        tmp_path,
        "conjugated",
        "---\nname: conjugated\ndescription: Uses a conjugated failure word.\n---\n\n"
        "Operations MUST be processed.\n\n"
        "## Steps\n\n"
        "1. Process the operation.\n"
        "2. Verify the operation recovers cleanly if the backend restarts.\n",
    )
    audit = _audit(tmp_path)
    assert "MISSING_FAILURE_MODE" not in _classes(audit["findings"])


def test_missing_failure_mode_does_not_fire_with_pitfalls_heading(
    tmp_path: Path,
) -> None:
    """Invariant: a 'Common Pitfalls' section is failure-mode content even
    when its bullets never use any of the check's vocabulary words.
    Mutation: remove the heading signal -> red.
    See docs/evidence/2026-10-02-missing-failure-mode-audit/FINDINGS.md,
    mechanism 2."""
    _write_skill(
        tmp_path,
        "pitfalls",
        "---\nname: pitfalls\ndescription: Documents pitfalls without failure vocabulary.\n---\n\n"
        "Operations MUST be processed.\n\n"
        "## Steps\n\n"
        "1. Process the operation.\n"
        "2. Return the result.\n\n"
        "## Common Pitfalls\n\n"
        "- Using a stale token instead of refreshing it first.\n",
    )
    audit = _audit(tmp_path)
    assert "MISSING_FAILURE_MODE" not in _classes(audit["findings"])


def test_missing_failure_mode_does_not_fire_on_invalid(
    tmp_path: Path,
) -> None:
    """Invariant: "invalid" names a rejection/error outcome without using
    "fail"/"error" literally -- real failure handling, not a gap. Found
    via a held-out run (TerminalSkills/skills): a literal try/catch
    returning "Invalid signature" (400) was flagged as having no failure
    mode at all.
    Mutation: remove "invalid" from the pattern list -> this test goes
    red. See docs/evidence/2026-10-04-held-out-corpora-adjudication/
    FINDINGS.md."""
    _write_skill(
        tmp_path,
        "invalid_signature",
        "---\nname: invalid_signature\ndescription: Verifies a webhook signature.\n---\n\n"
        "Operations MUST be processed.\n\n"
        "## Steps\n\n"
        "1. Verify the webhook signature.\n"
        "2. Return `Invalid signature` with status 400 if verification "
        "does not match.\n",
    )
    audit = _audit(tmp_path)
    assert "MISSING_FAILURE_MODE" not in _classes(audit["findings"])


def test_missing_failure_mode_does_not_fire_on_crash_denied_rejected(
    tmp_path: Path,
) -> None:
    """Invariant: "crash"/"denied"/"rejected" each name a failure outcome
    without "fail"/"error" literally. Found via a held-out run
    (TerminalSkills/skills): ssh's "fix permission denied and host key
    errors" and intercom's "a request without a valid jwt is rejected"
    were both flagged as having no failure mode at all.
    Mutation: remove these words from the pattern list -> this test goes
    red. See docs/evidence/2026-10-04-held-out-corpora-adjudication/
    FINDINGS.md."""
    _write_skill(
        tmp_path,
        "permission_denied",
        "---\nname: permission_denied\ndescription: SSH key setup.\n---\n\n"
        "Operations MUST be processed.\n\n"
        "## Steps\n\n"
        "1. Generate the key pair.\n"
        "2. Install the public key on the remote host.\n\n"
        "If the connection is denied, check the key permissions on the "
        "remote host; a request with the wrong key is rejected.\n",
    )
    audit = _audit(tmp_path)
    assert "MISSING_FAILURE_MODE" not in _classes(audit["findings"])


def test_missing_failure_mode_still_fires_with_unrelated_heading(
    tmp_path: Path,
) -> None:
    """Invariant: an unrelated heading must not be mistaken for a
    pitfalls-style section -- the heading guard is a real boundary.
    Mutation: over-broaden _FAILURE_MODE_HEADING -> red."""
    _write_skill(
        tmp_path,
        "unrelated_heading",
        "---\nname: unrelated_heading\ndescription: Has an unrelated heading, no failure content.\n---\n\n"
        "Operations MUST be processed.\n\n"
        "## Steps\n\n"
        "1. Process the operation.\n"
        "2. Return the result.\n\n"
        "## Additional Notes\n\n"
        "This section is unrelated to the procedure above.\n",
    )
    audit = _audit(tmp_path)
    assert "MISSING_FAILURE_MODE" in _classes(audit["findings"])


# ---------------------------------------------------------------------------
# NON_DETERMINISTIC_INSTRUCTION
# ---------------------------------------------------------------------------

def test_non_deterministic_fires_on_random(tmp_path: Path) -> None:
    """Invariant: 'random' without a seed is non-deterministic.
    Mutation: remove the non-determinism check -> this test goes red."""
    _write_skill(
        tmp_path,
        "random",
        "---\nname: random\ndescription: Random selection.\n---\n\n"
        "The agent MUST pick a random sample.\n",
    )
    audit = _audit(tmp_path)
    assert "NON_DETERMINISTIC_INSTRUCTION" in _classes(audit["findings"])
    finding = next(f for f in audit["findings"] if f["class"] == "NON_DETERMINISTIC_INSTRUCTION")
    assert finding["epistemic_status"] == "CANDIDATE"


def test_non_deterministic_does_not_fire_with_seed(tmp_path: Path) -> None:
    """Invariant: a seeded random is deterministic.
    Mutation: remove the seed pattern -> this test goes red."""
    _write_skill(
        tmp_path,
        "seeded",
        "---\nname: seeded\ndescription: Seeded selection.\n---\n\n"
        "The agent MUST pick a random sample with a fixed seed.\n",
    )
    audit = _audit(tmp_path)
    assert "NON_DETERMINISTIC_INSTRUCTION" not in _classes(audit["findings"])


def test_non_deterministic_fires_on_arbitrary(tmp_path: Path) -> None:
    """Invariant: 'arbitrary' without an anchor is non-deterministic.
    Mutation: remove 'arbitrary' from patterns -> this test goes red."""
    _write_skill(
        tmp_path,
        "arbitrary",
        "---\nname: arbitrary\ndescription: Arbitrary choice.\n---\n\n"
        "The agent MUST choose an arbitrary approach.\n",
    )
    audit = _audit(tmp_path)
    assert "NON_DETERMINISTIC_INSTRUCTION" in _classes(audit["findings"])


def test_non_deterministic_does_not_fire_on_pick_a(tmp_path: Path) -> None:
    """Invariant: 'pick a NOUN' is an ordinary indefinite article, not a
    claim of arbitrary choice -- only 'pick any NOUN' is.
    Mutation: restore bare 'a' to the pick/choose alternation -> this test
    goes red. See docs/evidence/2026-10-02-non-deterministic-instruction-
    false-positives/FINDINGS.md, mechanism 7."""
    _write_skill(
        tmp_path,
        "picker",
        "---\nname: picker\ndescription: Pick a type.\n---\n\n"
        "Pick a `type` that matches the kind. Use self-explanatory values.\n",
    )
    audit = _audit(tmp_path)
    assert "NON_DETERMINISTIC_INSTRUCTION" not in _classes(audit["findings"])


def test_non_deterministic_does_not_fire_on_choose_one_consistently(tmp_path: Path) -> None:
    """Invariant: 'choose/pick one X and stay consistent' commits to a single
    fixed choice -- it is an anti-non-determinism instruction, not an
    instance of non-determinism. Found via a held-out run against a fresh,
    previously unseen corpus (microsoft/skills): 35/35 NON_DETERMINISTIC_
    INSTRUCTION findings there were this exact templated sentence. 'one'
    shares the bare-article 'a' semantics (a specific single item), not
    'any's (no constraint on which) -- see docs/evidence/2026-10-04-
    held-out-corpora-adjudication/FINDINGS.md.
    Mutation: restore 'one' to the pick/choose alternation -> this test
    goes red."""
    _write_skill(
        tmp_path,
        "sync_or_async",
        "---\nname: sync_or_async\ndescription: Client usage.\n---\n\n"
        "Pick sync OR async and stay consistent. Do not mix sync clients "
        "with async clients in the same call path. Choose one mode per "
        "module.\n",
    )
    audit = _audit(tmp_path)
    assert "NON_DETERMINISTIC_INSTRUCTION" not in _classes(audit["findings"])


def test_non_deterministic_still_fires_on_pick_any(tmp_path: Path) -> None:
    """Invariant: 'pick any NOUN' is still a genuinely unconstrained choice.
    Mutation: over-narrow the pick/choose pattern -> this test goes red."""
    _write_skill(
        tmp_path,
        "picker_any",
        "---\nname: picker_any\ndescription: Pick any approach.\n---\n\n"
        "The agent MUST pick any approach that seems reasonable.\n",
    )
    audit = _audit(tmp_path)
    assert "NON_DETERMINISTIC_INSTRUCTION" in _classes(audit["findings"])


def test_non_deterministic_does_not_fire_on_negative_modality_rule(
    tmp_path: Path,
) -> None:
    """Invariant: a MUST_NOT/SHOULD_NOT/NEVER rule that forbids arbitrary
    behavior is not introducing the non-determinism it names -- it is
    prohibiting it.
    Mutation: remove the _NEGATIVE_MODALITIES guard -> this test goes red.
    See docs/evidence/2026-10-02-non-deterministic-instruction-false-
    positives/FINDINGS.md, mechanism 8."""
    _write_skill(
        tmp_path,
        "no_arbitrary",
        "---\nname: no_arbitrary\ndescription: No arbitrary thresholds.\n---\n\n"
        "The agent MUST NOT assign an arbitrary numeric threshold for this "
        "judgment.\n",
    )
    audit = _audit(tmp_path)
    assert "NON_DETERMINISTIC_INSTRUCTION" not in _classes(audit["findings"])


def test_non_deterministic_still_fires_on_positive_modality_rule(
    tmp_path: Path,
) -> None:
    """Invariant: a MUST rule that genuinely introduces arbitrary behavior
    must still fire -- the negative-modality guard must not suppress
    positive-modality rules.
    Mutation: over-broaden the _NEGATIVE_MODALITIES guard -> this test
    goes red."""
    _write_skill(
        tmp_path,
        "uses_arbitrary",
        "---\nname: uses_arbitrary\ndescription: Uses arbitrary thresholds.\n---\n\n"
        "The agent MUST assign an arbitrary numeric threshold for this "
        "judgment.\n",
    )
    audit = _audit(tmp_path)
    assert "NON_DETERMINISTIC_INSTRUCTION" in _classes(audit["findings"])


# ---------------------------------------------------------------------------
# IRREVERSIBLE_WITHOUT_REVIEW
# ---------------------------------------------------------------------------

def test_irreversible_without_review_fires_on_delete(tmp_path: Path) -> None:
    """Invariant: 'delete' without review is an unbounded irreversible action.
    Mutation: remove the irreversible check -> this test goes red."""
    _write_skill(
        tmp_path,
        "deleter",
        "---\nname: deleter\ndescription: Delete files.\n---\n\n"
        "The agent MUST delete the temporary files.\n",
    )
    audit = _audit(tmp_path)
    assert "IRREVERSIBLE_WITHOUT_REVIEW" in _classes(audit["findings"])
    finding = next(f for f in audit["findings"] if f["class"] == "IRREVERSIBLE_WITHOUT_REVIEW")
    assert finding["epistemic_status"] == "CANDIDATE"


def test_irreversible_without_review_does_not_fire_with_review(tmp_path: Path) -> None:
    """Invariant: 'delete' with review is bounded.
    Mutation: remove the review check -> this test goes red."""
    _write_skill(
        tmp_path,
        "safe_deleter",
        "---\nname: safe_deleter\ndescription: Safe deletion.\n---\n\n"
        "The agent MUST delete the temporary files after review.\n",
    )
    audit = _audit(tmp_path)
    assert "IRREVERSIBLE_WITHOUT_REVIEW" not in _classes(audit["findings"])


def test_irreversible_without_review_does_not_fire_on_never_delete_rule(tmp_path: Path) -> None:
    """Invariant: a MUST_NOT/SHOULD_NOT/NEVER rule prohibiting the
    irreversible action cannot be instructing the agent to perform it --
    same reasoning as the modality guard in NON_DETERMINISTIC_INSTRUCTION.
    Found via a held-out run against a fresh corpus (TerminalSkills/skills):
    "Never delete underperforming videos" was flagged as the dangerous
    unbounded delete it explicitly forbids. See docs/evidence/2026-10-04-
    held-out-corpora-adjudication/FINDINGS.md.
    Mutation: remove the modality guard -> this test goes red."""
    _write_skill(
        tmp_path,
        "never_deleter",
        "---\nname: never_deleter\ndescription: Retention policy.\n---\n\n"
        "Never delete underperforming videos -- they can resurface weeks "
        "later.\n",
    )
    audit = _audit(tmp_path)
    assert "IRREVERSIBLE_WITHOUT_REVIEW" not in _classes(audit["findings"])


def test_irreversible_without_review_does_not_fire_on_never_delete_step(tmp_path: Path) -> None:
    """Invariant: the same prohibition guard applies to procedural steps,
    which carry no `modality` field and so need the lexical starter check.
    Mutation: remove the step-side starter guard -> this test goes red."""
    _write_skill(
        tmp_path,
        "never_deleter_step",
        "---\nname: never_deleter_step\ndescription: Retention policy.\n---\n\n"
        "## Steps\n\n1. Never delete the archived snapshots.\n",
    )
    audit = _audit(tmp_path)
    assert "IRREVERSIBLE_WITHOUT_REVIEW" not in _classes(audit["findings"])


def test_irreversible_without_review_fires_on_force_push(tmp_path: Path) -> None:
    """Invariant: 'force-push' without backup is unbounded.
    Mutation: remove 'force-push' from patterns -> this test goes red."""
    _write_skill(
        tmp_path,
        "forcer",
        "---\nname: forcer\ndescription: Force push.\n---\n\n"
        "The agent MUST force-push to the main branch.\n",
    )
    audit = _audit(tmp_path)
    assert "IRREVERSIBLE_WITHOUT_REVIEW" in _classes(audit["findings"])


def test_irreversible_without_review_does_not_fire_with_rollback(tmp_path: Path) -> None:
    """Invariant: 'overwrite' with rollback is bounded.
    Mutation: remove 'rollback' from bound patterns -> this test goes red."""
    _write_skill(
        tmp_path,
        "safe_overwrite",
        "---\nname: safe_overwrite\ndescription: Safe overwrite.\n---\n\n"
        "The agent MUST overwrite the config file with a rollback plan.\n",
    )
    audit = _audit(tmp_path)
    assert "IRREVERSIBLE_WITHOUT_REVIEW" not in _classes(audit["findings"])


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_engineering_checks_are_deterministic(tmp_path: Path) -> None:
    """Invariant: the same input always produces the same findings.
    Mutation: introduce ordering randomness -> this test goes red."""
    _write_skill(
        tmp_path,
        "defect",
        "---\nname: defect\ndescription: Defective skill.\n---\n\n"
        "The agent MUST retry until success.\n"
        "The model MUST decide the outcome.\n"
        "This MUST always work.\n"
        "The agent MUST delete the files.\n\n"
        "## Steps\n\n"
        "1. Pick a random approach.\n"
        "2. Process the operation.\n",
    )
    audit1 = _audit(tmp_path)
    audit2 = _audit(tmp_path)
    assert audit1["audit_digest"] == audit2["audit_digest"]
    # Should have at least 4 of the 6 new check classes.
    new_classes = {
        "UNBOUNDED_RETRY", "LLM_IN_DECISION_PATH", "OVERCLAIM",
        "MISSING_FAILURE_MODE", "NON_DETERMINISTIC_INSTRUCTION",
        "IRREVERSIBLE_WITHOUT_REVIEW",
    }
    found = set(_classes(audit1["findings"]))
    assert len(found & new_classes) >= 4

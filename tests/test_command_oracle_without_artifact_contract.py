"""Falsifiable contract tests for the COMMAND_ORACLE_WITHOUT_ARTIFACT check."""

from __future__ import annotations

import tempfile
from pathlib import Path

from crucible.auditor import audit_corpus
from crucible.compiler import compile_corpus


def _audit(corpus: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        for name, content in corpus.items():
            d = root / name
            d.mkdir()
            (d / "SKILL.md").write_text(content, encoding="utf-8", newline="\n")
        ir = compile_corpus(root)
        return audit_corpus(ir)


def _findings_by_class(audit: dict, cls: str) -> list[dict]:
    return [f for f in audit["findings"] if f["class"] == cls]


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_flagged_for_bare_verb_without_artifact() -> None:
    """Invariant: a command-oracle check with a verb but no inline code
    is flagged. Mutation: skip the check -> red."""
    audit = _audit({
        "test": (
            "---\nname: test\ndescription: T.\nlicense: Apache-2.0\n---\n\n"
            "# T\n\nThe effect MUST be bounded.\n\n"
            "## Checks\n\n"
            "- Verify the effect is bounded.\n"
        ),
    })
    findings = _findings_by_class(audit, "COMMAND_ORACLE_WITHOUT_ARTIFACT")
    assert len(findings) >= 1
    assert findings[0]["epistemic_status"] == "CANDIDATE"


def test_not_flagged_for_inline_code_artifact() -> None:
    """Invariant: a command-oracle check backed by an inline code span
    is NOT flagged, regardless of leading verb.
    Mutation: flag inline-code checks too -> red."""
    audit = _audit({
        "test": (
            "---\nname: test\ndescription: T.\nlicense: Apache-2.0\n---\n\n"
            "# T\n\nThe effect MUST be bounded.\n\n"
            "## Checks\n\n"
            "- Run `scripts/validate.py` to confirm the bound.\n"
        ),
    })
    findings = _findings_by_class(audit, "COMMAND_ORACLE_WITHOUT_ARTIFACT")
    assert len(findings) == 0


def test_not_flagged_for_inline_code_naming_a_file() -> None:
    """Invariant: a backtick span naming a file (not a runnable command)
    is still enough to exempt the check -- consistent with
    CHECK_WITHOUT_ORACLE's own documented scope
    (test_oracle_kind_command_for_any_backtick_span_documents_real_scope).
    Mutation: require the backtick span to be a command -> red."""
    audit = _audit({
        "test": (
            "---\nname: test\ndescription: T.\nlicense: Apache-2.0\n---\n\n"
            "# T\n\nThe effect MUST be bounded.\n\n"
            "## Checks\n\n"
            "- Verify the `config.yaml` file exists in the repository.\n"
        ),
    })
    findings = _findings_by_class(audit, "COMMAND_ORACLE_WITHOUT_ARTIFACT")
    assert len(findings) == 0


def test_not_flagged_for_check_followed_by_fenced_block() -> None:
    """Invariant: a command-oracle check immediately followed by a
    fenced code block is NOT flagged, even though the check text itself
    has no inline code span -- the real-world "Run the server:\\n```bash
    \\n...\\n```" pattern. Measured on tests/fixtures/diverse-corpus:
    without this, fastapi/antigravity-support produced 3 false
    positives of this exact shape.
    Mutation: ignore fenced blocks, require inline code only -> red."""
    audit = _audit({
        "test": (
            "---\nname: test\ndescription: T.\nlicense: Apache-2.0\n---\n\n"
            "# T\n\nThe server MUST be started correctly.\n\n"
            "Run the development server:\n\n"
            "```bash\n"
            "fastapi dev\n"
            "```\n"
        ),
    })
    findings = _findings_by_class(audit, "COMMAND_ORACLE_WITHOUT_ARTIFACT")
    assert len(findings) == 0


def test_flagged_when_fenced_block_is_not_adjacent() -> None:
    """Invariant: a fenced block elsewhere in the body, separated by
    unrelated prose, does NOT exempt a vague check -- only a block
    immediately following (modulo blank lines) counts.
    Mutation: scan the whole body for any fenced block -> red."""
    audit = _audit({
        "test": (
            "---\nname: test\ndescription: T.\nlicense: Apache-2.0\n---\n\n"
            "# T\n\nThe server MUST be started correctly.\n\n"
            "## Checks\n\n"
            "- Verify the server started.\n\n"
            "Some unrelated explanation paragraph goes here.\n\n"
            "```bash\n"
            "fastapi dev\n"
            "```\n"
        ),
    })
    findings = _findings_by_class(audit, "COMMAND_ORACLE_WITHOUT_ARTIFACT")
    assert len(findings) == 1


def test_not_flagged_for_question_oracle() -> None:
    """Invariant: a check classified as oracle_kind 'question' is out of
    this check's scope entirely. Mutation: flag questions too -> red."""
    audit = _audit({
        "test": (
            "---\nname: test\ndescription: T.\nlicense: Apache-2.0\n---\n\n"
            "# T\n\nThe effect MUST be bounded.\n\n"
            "## Checks\n\n"
            "- Is the budget recorded?\n"
        ),
    })
    findings = _findings_by_class(audit, "COMMAND_ORACLE_WITHOUT_ARTIFACT")
    assert len(findings) == 0


def test_not_flagged_for_checkbox_oracle() -> None:
    """Invariant: a checkbox-style check is out of this check's scope.
    Mutation: flag checkboxes too -> red."""
    audit = _audit({
        "test": (
            "---\nname: test\ndescription: T.\nlicense: Apache-2.0\n---\n\n"
            "# T\n\nThe effect MUST be bounded.\n\n"
            "## Checks\n\n"
            "- [ ] Confirm the limit is enforced.\n"
        ),
    })
    findings = _findings_by_class(audit, "COMMAND_ORACLE_WITHOUT_ARTIFACT")
    assert len(findings) == 0


def test_not_flagged_for_unknown_oracle() -> None:
    """Invariant: a check with no recognizable oracle at all is
    CHECK_WITHOUT_ORACLE's territory, not this check's.
    Mutation: flag unknown-oracle checks too -> red."""
    audit = _audit({
        "test": (
            "---\nname: test\ndescription: T.\nlicense: Apache-2.0\n---\n\n"
            "# T\n\nThe effect MUST be bounded.\n\n"
            "## Checks\n\n"
            "- The sky is blue.\n"
        ),
    })
    findings = _findings_by_class(audit, "COMMAND_ORACLE_WITHOUT_ARTIFACT")
    assert len(findings) == 0


def test_mixed_checks_only_bare_verb_flagged() -> None:
    """Invariant: among several checks, only the bare-verb command
    oracle is flagged. Mutation: flag all or none -> red."""
    audit = _audit({
        "test": (
            "---\nname: test\ndescription: T.\nlicense: Apache-2.0\n---\n\n"
            "# T\n\nThe effect MUST be bounded.\n\n"
            "## Checks\n\n"
            "- Verify the effect is bounded.\n"
            "- Run `scripts/validate.py` to confirm the bound.\n"
            "- Is the budget recorded?\n"
            "- [ ] Confirm the limit is enforced.\n"
        ),
    })
    findings = _findings_by_class(audit, "COMMAND_ORACLE_WITHOUT_ARTIFACT")
    assert len(findings) == 1
    assert "check-0001" in findings[0]["evidence"]


# ---------------------------------------------------------------------------
# Evidence and limitation
# ---------------------------------------------------------------------------

def test_evidence_names_check_id() -> None:
    """Invariant: the evidence mentions the check id. Mutation: omit
    the check id -> red (untraceable)."""
    audit = _audit({
        "test": (
            "---\nname: test\ndescription: T.\nlicense: Apache-2.0\n---\n\n"
            "# T\n\nThe effect MUST be bounded.\n\n"
            "## Checks\n\n- Verify the effect is bounded.\n"
        ),
    })
    findings = _findings_by_class(audit, "COMMAND_ORACLE_WITHOUT_ARTIFACT")
    assert len(findings) >= 1
    assert "check-" in findings[0]["evidence"]


def test_has_limitation_documented() -> None:
    """Invariant: the finding documents the inline-code-only detection
    limitation. Mutation: claim full coverage -> red."""
    audit = _audit({
        "test": (
            "---\nname: test\ndescription: T.\nlicense: Apache-2.0\n---\n\n"
            "# T\n\nThe effect MUST be bounded.\n\n"
            "## Checks\n\n- Verify the effect is bounded.\n"
        ),
    })
    findings = _findings_by_class(audit, "COMMAND_ORACLE_WITHOUT_ARTIFACT")
    assert len(findings) >= 1
    assert findings[0]["limitation"] is not None
    assert "inline code" in findings[0]["limitation"].lower()


def test_has_source_evidence() -> None:
    """Invariant: the finding points to the check. Mutation: emit
    without source_span -> red."""
    audit = _audit({
        "test": (
            "---\nname: test\ndescription: T.\nlicense: Apache-2.0\n---\n\n"
            "# T\n\nThe effect MUST be bounded.\n\n"
            "## Checks\n\n- Verify the effect is bounded.\n"
        ),
    })
    findings = _findings_by_class(audit, "COMMAND_ORACLE_WITHOUT_ARTIFACT")
    assert len(findings) >= 1
    assert findings[0]["source_span"] is not None
    assert findings[0]["rule_id"] is not None


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_is_deterministic() -> None:
    """Invariant: two audits produce the same digest. Mutation: introduce
    non-determinism -> red."""
    corpus = {
        "test": (
            "---\nname: test\ndescription: T.\nlicense: Apache-2.0\n---\n\n"
            "# T\n\nThe effect MUST be bounded.\n\n"
            "## Checks\n\n- Verify the effect is bounded.\n"
        ),
    }
    audit1 = _audit(corpus)
    audit2 = _audit(corpus)
    assert audit1["audit_digest"] == audit2["audit_digest"]

"""Contract tests for the L15 final report assembler."""

from pathlib import Path

from crucible.confirm import MockConfirmExecutor
from crucible.final_report import build_final_report
from crucible.narrator import MockNarrationExecutor


def _write_skill(root: Path, name: str, body: str) -> None:
    skill = root / name
    skill.mkdir()
    (skill / "SKILL.md").write_text(body, encoding="utf-8", newline="\n")


def test_final_report_assembles_all_levels_for_the_readme_demo_fixture():
    report = build_final_report(
        "tests/fixtures/readme-demo",
        MockConfirmExecutor(),
        MockNarrationExecutor(),
    )
    assert report["schema_version"] == "crucible-final-report/v2"
    assert report["skill_count"] == 1
    assert "retry-example" in report["skills"]
    skill = report["skills"]["retry-example"]
    assert skill["recommendation"] in {"KEEP", "NEEDS_CONFIRMATION", "MODIFY", "CONSOLIDATE"}
    assert isinstance(skill["findings"], list)
    assert report["summary"]["total_skills"] == 1
    assert sum(report["summary"]["by_recommendation"].values()) == 1


def test_final_report_is_deterministic_for_identical_inputs():
    report_a = build_final_report(
        "tests/fixtures/readme-demo", MockConfirmExecutor(), MockNarrationExecutor()
    )
    report_b = build_final_report(
        "tests/fixtures/readme-demo", MockConfirmExecutor(), MockNarrationExecutor()
    )
    assert report_a["report_digest"] == report_b["report_digest"]


def test_final_report_does_not_retain_the_corpus_root_path():
    report = build_final_report(
        "tests/fixtures/readme-demo", MockConfirmExecutor(), MockNarrationExecutor()
    )
    assert "corpus_root" not in report
    assert "tests/fixtures/readme-demo" not in str(report)


def test_a_clean_skill_still_appears_in_the_report_as_keep(tmp_path: Path) -> None:
    """Invariant: skill_count (the true corpus size) must equal
    summary.total_skills and len(skills) -- every skill gets an entry,
    including one with zero findings, so the rendered report's header
    count is never silently higher than what the body actually lists.
    Confirmed as a real gap otherwise: a clean skill had no entry at
    all, not even KEEP, so the Markdown/HTML/PDF header's stated
    skill_count exceeded the number of skill sections actually
    rendered.
    Mutation: drop the all_skill_names pass-through in build_final_report
    -> this test goes red."""
    _write_skill(
        tmp_path,
        "clean-skill",
        "---\nname: clean-skill\ndescription: Short.\n---\n\nNothing here.\n",
    )
    _write_skill(
        tmp_path,
        "bad-skill",
        "---\nname: bad-skill\ndescription: Retries without a bound.\n---\n\n"
        "Operations MUST retry until success.\n",
    )
    report = build_final_report(
        str(tmp_path), MockConfirmExecutor(), MockNarrationExecutor()
    )
    assert report["skill_count"] == 2
    assert report["summary"]["total_skills"] == 2
    assert len(report["skills"]) == 2
    assert "clean-skill" in report["skills"]
    assert report["skills"]["clean-skill"]["recommendation"] == "KEEP"
    assert report["skills"]["clean-skill"]["findings"] == []
    assert report["skills"]["clean-skill"]["narration_blocked"] is False


_DEPLOY_FAST = """---
name: deploy-fast
description: Ship releases to production quickly.
license: Apache-2.0
---

# Deploy fast

Releases MUST skip the staging environment.

## Checks

- Verify the release reached production: run `scripts/check_prod.sh`.
"""

_DEPLOY_SAFE = """---
name: deploy-safe
description: Ship releases to production after verification.
license: Apache-2.0
---

# Deploy safely

Releases MUST NOT skip the staging environment.

## Checks

- Verify staging passed: run `scripts/check_staging.sh`.
"""


def test_a_contradiction_reaches_both_skills_and_carries_its_risk(tmp_path) -> None:
    """Invariant: a conflict between two skills is reported in the corpus
    section with its fixed risk statement, and BOTH skills are told to act
    on it. Before, the skill the finding was not attributed to read KEEP
    with "no findings".
    Mutation: drop the contradiction_parties fan-out -> deploy-safe KEEP -> red."""
    from crucible.final_report import CONTRADICTION_RISK
    from crucible.final_report_render import render_final_report_markdown

    _write_skill(tmp_path, "deploy-fast", _DEPLOY_FAST)
    _write_skill(tmp_path, "deploy-safe", _DEPLOY_SAFE)
    report = build_final_report(str(tmp_path), MockConfirmExecutor(), MockNarrationExecutor())

    [conflict] = report["corpus"]["contradictions"]
    assert conflict["class"] == "NORMATIVE_CONFLICT"
    assert conflict["risk"] == CONTRADICTION_RISK["NORMATIVE_CONFLICT"]
    for name in ("deploy-fast", "deploy-safe"):
        assert report["skills"][name]["recommendation"] == "MODIFY"
        assert conflict["finding_id"] in report["skills"][name]["confirmed_finding_ids"]
    text = render_final_report_markdown(report)
    assert "Risk: An agent that loads both rules" in text


def test_abstained_contradiction_check_is_not_reported_as_agreement(tmp_path) -> None:
    """Invariant: when the contradiction checks abstain, the report says they
    were not evaluated, never that no contradiction was found.
    Mutation: render the 'none found' line regardless of preconditions -> red."""
    from crucible.final_report_render import render_final_report_markdown

    _write_skill(tmp_path, "deploy-fast", _DEPLOY_FAST.replace(
        "Releases MUST skip the staging environment.", "Never skip staging."))
    report = build_final_report(str(tmp_path), MockConfirmExecutor(), MockNarrationExecutor())
    text = render_final_report_markdown(report)
    assert report["corpus"]["contradictions"] == []
    assert "Not evaluated: the contradiction checks abstained" in text
    assert "No contradiction found" not in text

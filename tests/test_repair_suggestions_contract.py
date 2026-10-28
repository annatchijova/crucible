"""Contract tests for gated rewrite suggestions in the narrated report."""

from __future__ import annotations

from pathlib import Path

from crucible.bob import LLMProposer, RuleBasedProposer
from crucible.confirm import MockConfirmExecutor
from crucible.final_report import build_final_report
from crucible.final_report_render import render_final_report_markdown
from crucible.narrator import MockNarrationExecutor


class ConfirmEverything(MockConfirmExecutor):
    """Test double: every single-skill candidate is confirmed, so skills
    reach MODIFY without depending on the mock's line-count heuristic."""

    def _execute_single(self, system_prompt, user_prompt, skill_text):
        return self._response(system_prompt, user_prompt, "CONFIRMED", "test: confirm all")


def _skill(name: str, rule: str) -> str:
    return (
        f"---\nname: {name}\ndescription: Handle {name} for outbound requests.\n---\n\n"
        f"# {name}\n\n{rule}\n\n## Steps\n\n1. Apply the rule to the request.\n"
    )


def _write(root: Path, corpus: dict[str, str]) -> str:
    for name, text in corpus.items():
        (root / name).mkdir()
        (root / name / "SKILL.md").write_text(text, encoding="utf-8", newline="\n")
    return str(root)


def _report(root: str, proposer, limit: int = 10):
    return build_final_report(
        root, ConfirmEverything(), MockNarrationExecutor(),
        repair_proposer=proposer, repair_limit=limit,
    )


def test_a_rewrite_that_removes_the_finding_is_accepted_with_its_diff(tmp_path) -> None:
    """Invariant: a MODIFY skill gets one rewrite, re-audited; it is ACCEPTED
    only because the targeted class is gone and nothing new appeared, and
    the report shows the change and the text-only limitation.
    Mutation: accept without re-auditing -> resolved_classes empty -> red."""
    root = _write(tmp_path, {"timeouts": _skill("timeouts", "Requests MUST use a 5 second timeout.")})
    report = _report(root, RuleBasedProposer())
    skill = report["skills"]["timeouts"]
    assert skill["recommendation"] == "MODIFY"
    rewrite = skill["suggested_rewrite"]
    assert rewrite["target_classes"] == ["REQUIREMENT_WITHOUT_CHECK"]
    assert rewrite["outcome"] == "ACCEPTED"
    assert rewrite["resolved_classes"] == ["REQUIREMENT_WITHOUT_CHECK"]
    assert rewrite["behavioral_gate"] is None
    assert "+## Checks" in rewrite["diff"]
    assert report["corpus"]["repairs"]["accepted"] == 1
    text = render_final_report_markdown(report)
    assert "Suggested rewrite (rule-based): ACCEPTED" in text
    assert "not evidence that an agent following it behaves better" in text


class AddsUnboundedRetry:
    """Fixes the missing check but also writes an unbounded retry."""

    def propose(self, finding, skill_text, context):
        return {
            "proposed_text": skill_text.rstrip() + (
                "\n\nRetries MUST continue until success.\n\n"
                "## Checks\n\n- Is a timeout set on every request?\n"
            ),
            "rationale": "test double",
            "proposer": "adds-unbounded-retry",
        }


def test_a_rewrite_that_introduces_a_finding_is_rejected(tmp_path) -> None:
    """Invariant: removing the targeted finding is not enough; a rewrite
    that brings in a finding the skill did not have is REJECTED and names it.
    Mutation: drop the novelty comparison -> ACCEPTED -> red."""
    root = _write(tmp_path, {"timeouts": _skill("timeouts", "Requests MUST use a 5 second timeout.")})
    rewrite = _report(root, AddsUnboundedRetry())["skills"]["timeouts"]["suggested_rewrite"]
    assert rewrite["outcome"] == "REJECTED"
    assert rewrite["rejection_reason"] == "NEW_FINDINGS"
    assert "UNBOUNDED_RETRY on timeouts" in rewrite["new_findings"]


def test_the_limit_is_deterministic_and_the_rest_is_listed(tmp_path) -> None:
    """Invariant: over the limit, skills are taken by most confirmed findings
    then name, and every skill left out is named, not silently dropped."""
    root = _write(tmp_path, {
        "alpha": _skill("alpha", "Requests MUST use a 5 second timeout."),
        "beta": _skill("beta", "Responses MUST be validated against the schema."),
    })
    report = _report(root, RuleBasedProposer(), limit=1)
    repairs = report["corpus"]["repairs"]
    assert repairs["eligible"] == 2
    assert repairs["attempted"] == 1
    [left_out] = repairs["not_attempted"]
    [chosen] = [n for n, s in report["skills"].items() if s.get("suggested_rewrite")]
    assert {chosen, left_out} == {"alpha", "beta"}
    count = {n: len(report["skills"][n]["confirmed_finding_ids"]) for n in ("alpha", "beta")}
    assert (-count[chosen], chosen) < (-count[left_out], left_out)


def test_without_a_key_the_rewrite_is_blocked_not_simulated(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    root = _write(tmp_path, {"timeouts": _skill("timeouts", "Requests MUST use a 5 second timeout.")})
    rewrite = _report(root, LLMProposer())["skills"]["timeouts"]["suggested_rewrite"]
    assert rewrite["outcome"] == "BLOCKED"
    assert rewrite["proposed_text"] is None

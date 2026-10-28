"""The call estimate must bound what a report actually spends."""

from __future__ import annotations

from pathlib import Path

from crucible.bob import RuleBasedProposer
from crucible.call_estimate import estimate_model_calls
from crucible.confirm import MockConfirmExecutor
from crucible.consolidation import UnionConsolidationProposer
from crucible.final_report import build_final_report
from crucible.narrator import MockNarrationExecutor


class _CountingConfirm(MockConfirmExecutor):
    """Confirms everything (the most expensive verdicts downstream)."""

    def __init__(self) -> None:
        super().__init__(threshold=0)
        self.calls = 0

    def execute(self, system_prompt, user_prompt):
        self.calls += 1
        return super().execute(system_prompt, user_prompt)

    def _execute_single(self, system_prompt, user_prompt, skill_text):
        return self._response(system_prompt, user_prompt, "CONFIRMED", "test")


class _CountingNarration(MockNarrationExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def execute(self, system_prompt, user_prompt):
        self.calls += 1
        return super().execute(system_prompt, user_prompt)


class _Counting:
    def __init__(self, inner) -> None:
        self.inner, self.calls = inner, 0

    def propose(self, *args):
        self.calls += 1
        return self.inner.propose(*args)

    def propose_merge(self, *args):
        self.calls += 1
        return self.inner.propose_merge(*args)


def _skill(name: str, body: str) -> str:
    return f"---\nname: {name}\ndescription: Retry failed network calls with a budget.\n---\n\n{body}\n"


CORPUS = {
    "retry-a": _skill("retry-a", "# Retry\n\nRetries MUST have a finite budget.\n\nBackoff MUST be exponential."),
    "retry-b": _skill("retry-b", "# Retry\n\nRetries MUST have a finite budget.\n\nBackoff MUST be exponential."),
    "retry-c": _skill("retry-c", "# Retry\n\nRetries MUST have a finite budget.\n\nBackoff MUST be exponential."),
    "timeouts": _skill("timeouts", "# Timeouts\n\nRequests MUST use a 5 second timeout.\n\nRetry until it works."),
    "schema": _skill("schema", "# Schema\n\nResponses MUST be validated against the schema."),
}


def test_every_stage_stays_within_its_estimated_bound(tmp_path: Path) -> None:
    """Invariant: with every verdict CONFIRMED, the calls actually made per
    stage never exceed the estimate, and confirmation matches it exactly.
    Mutation: drop a class from the confirmable set in the estimate -> the
    confirmation count exceeds it -> red."""
    for name, text in CORPUS.items():
        (tmp_path / name).mkdir()
        (tmp_path / name / "SKILL.md").write_text(text, encoding="utf-8", newline="\n")

    estimate = estimate_model_calls(
        str(tmp_path), with_consolidation=True, with_repairs=True, repair_limit=2
    )["max_calls_by_stage"]

    confirm, narration = _CountingConfirm(), _CountingNarration()
    merger = _Counting(UnionConsolidationProposer())
    repairer = _Counting(RuleBasedProposer())
    report = build_final_report(
        str(tmp_path), confirm, narration,
        consolidation_proposer=merger, repair_proposer=repairer, repair_limit=2,
    )

    assert confirm.calls == estimate["confirmation"]
    assert narration.calls <= estimate["narration"] + estimate["executive_summary"]
    assert merger.calls <= estimate["consolidation"]
    assert repairer.calls <= estimate["repairs"]
    # The corpus exercises every stage, so the bound is not vacuous.
    assert merger.calls >= 1 and repairer.calls >= 1 and narration.calls >= 2
    assert report["corpus"]["consolidation_groups"][0]["size"] == 3

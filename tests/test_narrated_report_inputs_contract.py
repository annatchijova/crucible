"""Contract tests for the narrated report's inputs and its L16 section.

The report must accept what a user actually has -- one SKILL.md, a
directory, or the installed skills -- and say which one it was given.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from crucible.cli import main
from crucible.confirm import MockConfirmExecutor
from crucible.consolidation import CONSOLIDATION_FIXTURE, UnionConsolidationProposer
from crucible.final_report import build_final_report
from crucible.final_report_render import render_final_report_markdown
from crucible.narrator import MockNarrationExecutor


def _twin(name: str) -> str:
    return (
        f"---\nname: {name}\n"
        "description: Retry failed network calls with a bounded budget.\n"
        "license: Apache-2.0\n---\n\n# Retry network calls\n\n"
        "Retries MUST have a finite budget.\n\n"
        "Backoff MUST be exponential.\n\n"
        "## Checks\n\n- Verify the retry budget is enforced: run `scripts/check_budget.sh`.\n"
    )


# MockConfirmExecutor confirms a pair only above 80% shared lines, so the
# duplicate pair here differs in its name line alone.
CORPUS = {
    "retry-a": _twin("retry-a"),
    "retry-b": _twin("retry-b"),
    "unrelated": CONSOLIDATION_FIXTURE["unrelated"],
}


def _write_corpus(root: Path, corpus: dict[str, str]) -> None:
    for name, text in corpus.items():
        (root / name).mkdir()
        (root / name / "SKILL.md").write_text(text, encoding="utf-8", newline="\n")


def _run(argv: list[str], capsys) -> tuple[int, str]:
    saved = sys.argv
    try:
        sys.argv = ["crucible", *argv]
        code = main()
    finally:
        sys.argv = saved
    return code, capsys.readouterr().out


def test_consolidation_section_carries_the_gate_verdict_per_group(tmp_path) -> None:
    """Invariant: with a proposer, every duplicate group gets one proposal
    and the gate's verdict, and an accepted merge's text is shown.
    Mutation: skip _consolidation_section -> no proposals -> red."""
    _write_corpus(tmp_path, CORPUS)
    report = build_final_report(
        str(tmp_path), MockConfirmExecutor(), MockNarrationExecutor(),
        consolidation_proposer=UnionConsolidationProposer(),
    )
    [group] = report["corpus"]["consolidation_groups"]
    assert group["members"] == ["retry-a", "retry-b"]
    [proposal] = report["corpus"]["consolidation"]["proposals"]
    assert proposal["members"] == ["retry-a", "retry-b"]
    assert proposal["outcome"] == "ACCEPTED"
    assert report["corpus"]["consolidation"]["behavioral_gate"] is None
    text = render_final_report_markdown(report)
    assert "Proposed merge `retry-a-consolidated` (union-mock): ACCEPTED" in text
    assert "name: retry-a-consolidated" in text


def test_without_a_proposer_no_merge_is_claimed(tmp_path) -> None:
    """Invariant: the default report recommends consolidation but never
    claims a merge was proposed or checked."""
    _write_corpus(tmp_path, CORPUS)
    report = build_final_report(str(tmp_path), MockConfirmExecutor(), MockNarrationExecutor())
    assert "consolidation" not in report["corpus"]
    assert "Proposed merge" not in render_final_report_markdown(report)


def test_cli_narrates_a_single_skill_file(tmp_path, capsys) -> None:
    """Invariant: a bare SKILL.md path is accepted and reported as one skill
    file, and the cross-skill sections say why they are empty.
    Mutation: pass the file straight to compile_corpus -> no skill -> red."""
    _write_corpus(tmp_path, {"retry-a": CORPUS["retry-a"]})
    code, out = _run([str(tmp_path / "retry-a" / "SKILL.md"), "--mock-narrate"], capsys)
    report = json.loads(out)
    assert code == 0
    assert report["input"]["scope"] == "single-skill"
    assert report["skill_count"] == 1
    text = render_final_report_markdown(report)
    assert "Only one skill was scanned" in text


def test_cli_narrates_installed_skills_with_their_coverage(tmp_path, capsys) -> None:
    """Invariant: --scan-installed with --narrate reports on the staged
    installed packages and carries the installed scan's coverage."""
    _write_corpus(tmp_path, CORPUS)
    code, out = _run(["--scan-installed", "--scan-root", str(tmp_path), "--mock-narrate"], capsys)
    report = json.loads(out)
    assert code == 0
    assert report["input"]["scope"] == "installed"
    assert report["input"]["coverage"]["analyzed"] == 3
    assert report["summary"]["by_recommendation"]["CONSOLIDATE"] == 2


def test_cli_renders_the_narrated_report_directly(tmp_path, capsys) -> None:
    _write_corpus(tmp_path, CORPUS)
    code, out = _run(
        [str(tmp_path), "--mock-narrate", "--with-consolidation", "--render-format", "markdown"],
        capsys,
    )
    assert code == 0
    assert out.startswith("# Crucible Skill Quality Report")
    assert "2 skills into 1: retry-a, retry-b" in out
    assert "ACCEPTED by the deterministic gate" in out

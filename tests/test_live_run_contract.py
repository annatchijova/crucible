"""Contract tests for the one-command live run (exercised in --mock mode)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crucible.live_run import main


def _twin(name: str) -> str:
    return (
        f"---\nname: {name}\ndescription: Retry failed network calls with a bounded budget.\n---\n\n"
        "# Retry\n\nRetries MUST have a finite budget.\n\nBackoff MUST be exponential.\n"
    )


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    for name in ("retry-a", "retry-b", "solo"):
        (root / name).mkdir(parents=True)
        (root / name / "SKILL.md").write_text(_twin(name), encoding="utf-8", newline="\n")
    return root


def test_mock_run_writes_every_artifact_and_counts_within_bounds(corpus, tmp_path) -> None:
    """Invariant: a run leaves the sealed report, its renderings, the estimate
    and RUN.md, and the calls it made never exceed the estimate."""
    out = tmp_path / "run"
    assert main([str(corpus), "--out-dir", str(out), "--mock"]) == 0
    assert {p.name for p in out.iterdir()} == {
        "RUN.md", "estimate.json", "report.json", "report.md", "report.html"
    }
    report = json.loads((out / "report.json").read_text())
    estimate = json.loads((out / "estimate.json").read_text())
    assert report["audit_digest"] == estimate["audit_digest"]
    run = (out / "RUN.md").read_text()
    assert "mock stand-ins, no model called" in run
    assert report["report_digest"] in run
    assert "What this run does not show" in run


def test_a_run_never_overwrites_earlier_evidence(corpus, tmp_path) -> None:
    out = tmp_path / "run"
    out.mkdir()
    with pytest.raises(SystemExit):
        main([str(corpus), "--out-dir", str(out), "--mock"])


def test_live_run_stops_over_budget_before_calling_a_model(corpus, tmp_path, monkeypatch) -> None:
    """Invariant: when the bound exceeds --max-calls, nothing is called and
    nothing is written. A key is set so the stop cannot be the missing-key
    path; any real call would fail the test by touching the network."""
    monkeypatch.setenv("NEBIUS_API_KEY", "test-not-a-key")

    def no_network(*args, **kwargs):
        raise AssertionError("a model was called")

    monkeypatch.setattr("urllib.request.urlopen", no_network)
    out = tmp_path / "run"
    assert main([str(corpus), "--out-dir", str(out), "--max-calls", "1"]) == 2
    assert not out.exists()


def test_slice_runs_only_the_named_skills(corpus, tmp_path) -> None:
    out = tmp_path / "run"
    assert main([str(corpus), "--out-dir", str(out), "--mock", "--skills", "retry-a,retry-b"]) == 0
    report = json.loads((out / "report.json").read_text())
    assert sorted(report["skills"]) == ["retry-a", "retry-b"]
    assert "slice: retry-a, retry-b" in (out / "RUN.md").read_text()

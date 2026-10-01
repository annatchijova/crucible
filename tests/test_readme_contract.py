"""Executable examples and navigation shared by the three public documents."""
import io
import json
from pathlib import Path
import re
import sys

import pytest

from crucible.cli import main


ROOT = Path(__file__).resolve().parents[1]
DOCS = ("README.md", "README_ES.md", "TECHNICAL.md")
NAV = "[English](README.md) · [Español](README_ES.md) · **[Technical README](TECHNICAL.md)**"
EXPECTED = {"UNBOUNDED_RETRY", "REQUIREMENT_WITHOUT_CHECK", "METHODOLOGICAL_VACUITY"}


@pytest.mark.parametrize("stdin", [False, True])
def test_documented_example_emits_only_expected_candidates(stdin, monkeypatch, capsys):
    fixture = ROOT / "tests/fixtures/readme-demo/SKILL.md"
    if stdin:
        args = ["crucible", "--scan-skill"]
        monkeypatch.setattr(sys, "stdin", io.StringIO(fixture.read_text()))
    else:
        args = ["crucible", str(fixture.parent), "--no-graph"]
    monkeypatch.setattr(sys, "argv", args)
    assert main() == 0
    findings = json.loads(capsys.readouterr().out)["findings"]
    assert len(findings) == 3
    assert {finding["class"] for finding in findings} == EXPECTED
    assert {finding["epistemic_status"] for finding in findings} == {"CANDIDATE"}
    assert all(finding["source_span"]["line"] == 5 for finding in findings)


@pytest.mark.parametrize("name", DOCS)
def test_navigation_and_local_links(name):
    text = (ROOT / name).read_text()
    assert text.splitlines()[0] == NAV
    for link in re.findall(r"\]\(([^)]+)\)", text):
        if "://" in link:
            continue
        path, _, anchor = link.partition("#")
        target = ROOT / (path or name)
        assert target.exists(), (name, link)
        if anchor:
            headings = re.findall(r"^#+ (.+)$", target.read_text(), re.MULTILINE)
            slugs = {re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings}
            assert anchor in slugs, (name, link)


def test_readme_commands_and_fixture_stay_synchronized():
    english, spanish = [(ROOT / name).read_text() for name in DOCS[:2]]
    assert re.findall(r"```bash\n(.*?)```", english, re.DOTALL) == re.findall(
        r"```bash\n(.*?)```", spanish, re.DOTALL
    )
    fixture = (ROOT / "tests/fixtures/readme-demo/SKILL.md").read_text().strip()
    for text in (english, spanish):
        assert re.findall(r"```markdown\n(.*?)```", text, re.DOTALL)[0].strip() == fixture
        assert text.index('pip install -e ".[api]"') < text.index("--serve")

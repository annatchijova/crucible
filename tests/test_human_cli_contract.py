"""Falsifiable contract tests for the --human CLI flag wiring.

human_output.py is unit-tested on its own in
test_human_output_contract.py; these tests check that cli.py's --human
flag actually reaches it for real CLI invocations, end to end.
"""

from __future__ import annotations

import json
import sys

import pytest

from crucible.cli import main


def test_human_flag_renders_text_not_json_for_audit(tmp_path, monkeypatch, capsys):
    """Invariant: --human on a plain audit run produces readable text,
    not JSON. Mutation: ignore args.human in the audit code path -> red."""
    skill_dir = tmp_path / "retrier"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: retrier\ndescription: Retry things.\nlicense: Apache-2.0\n"
        "---\n\nRetries MUST be bounded.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv", ["crucible", str(tmp_path), "--no-graph", "--human"]
    )
    assert main() == 0
    out = capsys.readouterr().out
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)
    assert "Audit" in out


def test_without_human_flag_output_is_still_valid_json(tmp_path, monkeypatch, capsys):
    """Invariant: omitting --human preserves the exact pre-existing JSON
    behavior. Mutation: always render human text regardless of the flag
    -> red (breaks every machine consumer of the CLI)."""
    skill_dir = tmp_path / "retrier"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: retrier\ndescription: Retry things.\nlicense: Apache-2.0\n"
        "---\n\nRetries MUST be bounded.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["crucible", str(tmp_path), "--no-graph"])
    assert main() == 0
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["audit_digest"].startswith("sha256:")


def test_human_flag_renders_mutation_lab_as_text(monkeypatch, capsys):
    """Invariant: --human works for the mutation lab's own report shape,
    not just audits. Mutation: hardcode the audit renderer for every
    report -> red (crashes or mis-renders non-audit shapes)."""
    monkeypatch.setattr(sys, "argv", ["crucible", "--mutate", "--human"])
    assert main() == 0
    out = capsys.readouterr().out
    assert "Mutation lab" in out
    assert "kill rate" in out

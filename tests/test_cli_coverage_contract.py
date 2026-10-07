"""Installed scan coverage remains visible without changing legacy JSON."""
import json
import sys
from pathlib import Path

import pytest

from crucible.cli import main


@pytest.mark.parametrize('include_coverage', [False, True])
def test_installed_cli_reports_duplicate_omissions(tmp_path, monkeypatch, capsys, include_coverage):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    for root in ('.claude/skills', '.codex/skills'):
        package = tmp_path / root / 'sample'
        package.mkdir(parents=True)
        (package / 'SKILL.md').write_text(
            '---\nname: sample\ndescription: Sample.\n---\n1. Validate input.\n'
        )
    args = ['crucible', '--scan-installed']
    if include_coverage:
        args.append('--include-coverage')
    monkeypatch.setattr(sys, 'argv', args)
    assert main() == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert 'PARTIAL' in captured.err
    if include_coverage:
        assert result['coverage']['skipped'] == 1
        assert result['coverage']['analyzed'] == 1
        assert result['audit']['audit_digest'].startswith('sha256:')
    else:
        assert result['audit_digest'].startswith('sha256:')
        assert 'coverage' not in result


def test_coverage_flag_requires_installed_mode(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['crucible', '--mutate', '--include-coverage'])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


@pytest.mark.parametrize('include_coverage', [False, True])
def test_empty_installed_cli_keeps_coverage_opt_in(
    tmp_path, monkeypatch, capsys, include_coverage
):
    """Empty-scan coverage is additive; legacy error JSON stays unchanged."""
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    args = ['crucible', '--scan-installed']
    if include_coverage:
        args.append('--include-coverage')
    monkeypatch.setattr(sys, 'argv', args)

    assert main() == 1
    result = json.loads(capsys.readouterr().out)
    assert 'error' in result
    if include_coverage:
        assert result['coverage']['status'] == 'EMPTY'
        assert result['coverage']['discovered'] == 0
    else:
        assert 'coverage' not in result


def test_collection_limit_has_machine_readable_error(monkeypatch, capsys):
    def fail():
        raise ValueError('installed collection exceeds directory limit')
    monkeypatch.setattr('crucible.api.scan_installed_collection', fail)
    monkeypatch.setattr(sys, 'argv', ['crucible', '--scan-installed-collection'])
    assert main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'ERROR'
    assert 'directory limit' in result['error']

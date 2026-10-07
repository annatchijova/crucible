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


@pytest.mark.parametrize('collection_mode', [False, True])
def test_cli_scans_explicit_local_root(tmp_path, monkeypatch, capsys, collection_mode):
    roots = [tmp_path / 'external' / 'skills-a', tmp_path / 'external' / 'skills-b']
    for index, root in enumerate(roots):
        name = f'sample-{index}'
        relative = Path('namespace') / name if collection_mode else Path(name)
        package = root / relative / 'SKILL.md'
        package.parent.mkdir(parents=True)
        package.write_text(
            f'---\nname: {name}\ndescription: Sample.\n---\n1. Validate input.\n'
        )
    mode = '--scan-installed-collection' if collection_mode else '--scan-installed'
    args = ['crucible', mode]
    for root in roots:
        args.extend(['--scan-root', str(root)])
    if not collection_mode:
        args.append('--include-coverage')
    monkeypatch.setattr(sys, 'argv', args)

    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    coverage = result['coverage']
    assert coverage['searched'] == [str(root) for root in roots]
    assert coverage['discovered'] == coverage['analyzed'] == 2


def test_scan_root_requires_exactly_one_installed_mode(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['crucible', '--scan-root', '/tmp/skills', '--mutate'])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_installed_modes_are_mutually_exclusive(monkeypatch):
    monkeypatch.setattr('crucible.api.scan_installed_skills', lambda: pytest.fail('scanner invoked'))
    monkeypatch.setattr('crucible.api.scan_installed_collection', lambda: pytest.fail('scanner invoked'))
    monkeypatch.setattr(sys, 'argv', [
        'crucible', '--scan-installed', '--scan-installed-collection'
    ])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_explicit_missing_root_is_a_machine_readable_cli_error(tmp_path, monkeypatch, capsys):
    missing = tmp_path / 'missing'
    monkeypatch.setattr(sys, 'argv', [
        'crucible', '--scan-installed-collection', '--scan-root', str(missing)
    ])

    assert main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'ERROR'
    assert 'explicit scan root' in result['error']

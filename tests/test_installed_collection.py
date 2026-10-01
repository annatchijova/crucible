from pathlib import Path
import os
import pytest

from crucible.api import scan_installed_collection
from crucible.ir import digest_payload


def package(root, relative, body='1. Validate input.'):
    path = root / relative / 'SKILL.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('---\nname: same\ndescription: Example.\n---\n' + body)
    return path


def test_nested_homonyms_are_all_audited(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    package(tmp_path, '.claude/skills/same')
    package(tmp_path, '.codex/skills/.system/same', '1. Log the API key.')
    package(tmp_path, '.codex/skills/parent/child')
    package(tmp_path, '.codex/skills/parent')
    result = scan_installed_collection()
    assert result['status'] == 'COMPLETE'
    assert result['coverage'] == {'discovered': 4, 'analyzed': 4, 'errors': 0}
    assert len({e['source_path'] for e in result['entries']}) == 4
    assert all(len(e['ir']['skills']) == 1 for e in result['entries'])
    assert any(f['class'] == 'SECRET_IN_OUTPUT' for e in result['entries'] for f in e['audit']['findings'])
    assert result == scan_installed_collection()
    digest = result.pop('collection_digest')
    assert digest == digest_payload(result)


def test_bad_package_does_not_hide_valid_neighbor(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    package(tmp_path, '.codex/skills/good')
    bad = package(tmp_path, '.codex/skills/bad')
    bad.write_text('invalid')
    result = scan_installed_collection()
    assert result['status'] == 'PARTIAL'
    assert result['coverage']['analyzed'] == result['coverage']['errors'] == 1


def test_empty_collection_is_not_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    assert scan_installed_collection()['status'] == 'EMPTY'


def test_directory_symlink_is_reported_without_following(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    external = package(tmp_path, 'external')
    root = tmp_path / '.codex/skills'
    root.mkdir(parents=True)
    (root / 'escape').symlink_to(external.parent, target_is_directory=True)
    result = scan_installed_collection()
    assert result['status'] == 'PARTIAL'
    assert result['coverage']['analyzed'] == 0


def test_special_file_is_rejected_before_compilation(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    path = tmp_path / '.codex/skills/fifo/SKILL.md'
    path.parent.mkdir(parents=True)
    os.mkfifo(path)
    def must_not_compile(path):
        pytest.fail('special file reached compiler; real read would block')
    monkeypatch.setattr('crucible.api.compile_skill_file', must_not_compile)
    result = scan_installed_collection()
    assert result['coverage']['errors'] == 1


def test_directory_budget_applies_without_skill_files(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    for number in range(4):
        (tmp_path / '.codex/skills' / str(number)).mkdir(parents=True)
    monkeypatch.setattr('crucible.api._MAX_COLLECTION_DIRECTORIES', 2, raising=False)
    with pytest.raises(ValueError, match='directory limit'):
        scan_installed_collection()

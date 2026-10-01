import os
import shutil

import pytest

from crucible import api


TEXT = b'---\nname: safe\ndescription: Example.\n---\n'


@pytest.fixture
def package(tmp_path, monkeypatch):
    root = tmp_path / 'skills'
    package = root / 'safe'
    package.mkdir(parents=True)
    (package / 'SKILL.md').write_bytes(TEXT)
    monkeypatch.setattr(api, '_find_installed_skill_dirs', lambda: [root])
    return package


def test_staging_does_not_copy_unrelated_package_content(package, monkeypatch):
    (package / 'large-attachment').write_bytes(b'unneeded')
    monkeypatch.setattr(shutil, 'copytree', lambda *a, **k: pytest.fail('unbounded tree copy'))
    assert api.scan_installed_skills()['audit'] is not None


def test_staging_byte_budget_is_enforced_before_compilation(package, monkeypatch):
    monkeypatch.setattr(api, '_MAX_COLLECTION_BYTES', len(TEXT) - 1)
    monkeypatch.setattr(api, 'compile_corpus', lambda *a, **k: pytest.fail('compiled over budget'))
    with pytest.raises(ValueError, match='byte limit'):
        api.scan_installed_skills()


def test_staging_preserves_nested_skill_paths(package):
    nested = package / 'nested'
    nested.mkdir()
    (nested / 'SKILL.md').write_bytes(TEXT.replace(b'name: safe', b'name: nested'))
    result = api.scan_installed_skills()
    assert {s['identity']['source_path'] for s in result['ir']['skills']} == {
        'safe/SKILL.md', 'safe/nested/SKILL.md',
    }


def test_staging_skill_cap_precedes_compilation(package, monkeypatch):
    monkeypatch.setattr(api, '_MAX_SCAN_SKILLS', 0)
    monkeypatch.setattr(api, 'compile_corpus', lambda *a, **k: pytest.fail('compiled over budget'))
    with pytest.raises(ValueError, match='limit'):
        api.scan_installed_skills()


def test_staging_budget_is_shared_and_accepts_exact_total(package, monkeypatch):
    other = package.parent / 'other'
    other.mkdir()
    other_text = TEXT.replace(b'name: safe', b'name: other')
    (other / 'SKILL.md').write_bytes(other_text)
    total = len(TEXT) + len(other_text)
    monkeypatch.setattr(api, '_MAX_COLLECTION_BYTES', total)
    assert len(api.scan_installed_skills()['ir']['skills']) == 2
    monkeypatch.setattr(api, '_MAX_COLLECTION_BYTES', total - 1)
    with pytest.raises(ValueError, match='byte limit'):
        api.scan_installed_skills()


def test_staging_rejects_fifo_without_reading(package, monkeypatch):
    source = package / 'SKILL.md'
    source.unlink()
    os.mkfifo(source)
    monkeypatch.setattr(os, 'read', lambda *a: pytest.fail('FIFO was read'))
    with pytest.raises(ValueError, match='regular file'):
        api.scan_installed_skills()


def test_staging_rejects_source_replacement_after_discovery(package, monkeypatch):
    original = api._discover_corpus

    def swap(*args, **kwargs):
        paths = original(*args, **kwargs)
        source = package / 'SKILL.md'
        source.rename(package / 'old.md')
        source.write_bytes(TEXT.replace(b'name: safe', b'name: hostile'))
        return paths

    monkeypatch.setattr(api, '_discover_corpus', swap)
    with pytest.raises(ValueError, match='identity changed'):
        api.scan_installed_skills()


def test_staging_ignores_unrelated_fifo(package):
    os.mkfifo(package / 'unrelated-pipe')
    assert api.scan_installed_skills()['audit'] is not None

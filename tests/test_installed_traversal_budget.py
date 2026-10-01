import pytest

from crucible import api, compiler


TEXT = b'---\nname: safe\ndescription: Example.\n---\n'


def roots_with_skills(tmp_path, monkeypatch):
    roots = [tmp_path / 'first', tmp_path / 'second']
    for index, root in enumerate(roots):
        package = root / f'skill-{index}'
        package.mkdir(parents=True)
        (package / 'SKILL.md').write_bytes(TEXT.replace(b'safe', f'skill-{index}'.encode()))
    monkeypatch.setattr(api, '_find_installed_skill_dirs', lambda: roots)
    return roots


def test_initial_listing_counts_unrelated_entries(tmp_path, monkeypatch):
    root = tmp_path / 'skills'
    root.mkdir()
    for name in ('a', 'b', 'c'):
        (root / name).touch()
    monkeypatch.setattr(api, '_find_installed_skill_dirs', lambda: [root])
    monkeypatch.setattr(compiler, '_MAX_CORPUS_ENTRIES', 2)
    with pytest.raises(ValueError, match='entry limit'):
        api.scan_installed_skills()


def test_entry_budget_is_shared_across_roots_and_packages(tmp_path, monkeypatch):
    roots_with_skills(tmp_path, monkeypatch)
    monkeypatch.setattr(compiler, '_MAX_CORPUS_ENTRIES', 3)
    monkeypatch.setattr(api, 'compile_corpus', lambda *a, **k: pytest.fail('source limit was deferred'))
    with pytest.raises(ValueError, match='entry limit'):
        api.scan_installed_skills()


def test_directory_budget_is_shared_across_roots_and_packages(tmp_path, monkeypatch):
    roots_with_skills(tmp_path, monkeypatch)
    monkeypatch.setattr(compiler, '_MAX_CORPUS_DIRECTORIES', 3)
    with pytest.raises(ValueError, match='directory limit'):
        api.scan_installed_skills()


def test_exact_global_discovery_budgets_are_accepted(tmp_path, monkeypatch):
    roots_with_skills(tmp_path, monkeypatch)
    monkeypatch.setattr(compiler, '_MAX_CORPUS_ENTRIES', 4)
    monkeypatch.setattr(compiler, '_MAX_CORPUS_DIRECTORIES', 4)
    assert len(api.scan_installed_skills()['ir']['skills']) == 2


def test_initial_listing_stops_at_first_excess_entry(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace

    consumed = []

    def children():
        for name in ('a', 'b', 'c'):
            consumed.append(name)
            yield SimpleNamespace(name=name, is_dir=lambda **kwargs: False)
        pytest.fail('enumeration continued beyond the first excess entry')

    @contextmanager
    def scan(root, **kwargs):
        yield children()

    monkeypatch.setattr(api, '_scan_corpus_directory', scan)
    monkeypatch.setattr(api, '_find_installed_skill_dirs', lambda: [tmp_path])
    monkeypatch.setattr(compiler, '_MAX_CORPUS_ENTRIES', 2)
    with pytest.raises(ValueError, match='entry limit'):
        api.scan_installed_skills()
    assert consumed == ['a', 'b', 'c']


def test_empty_roots_share_directory_budget(tmp_path, monkeypatch):
    roots = [tmp_path / 'one', tmp_path / 'two']
    for root in roots:
        root.mkdir()
    monkeypatch.setattr(api, '_find_installed_skill_dirs', lambda: roots)
    monkeypatch.setattr(compiler, '_MAX_CORPUS_DIRECTORIES', 1)
    with pytest.raises(ValueError, match='directory limit'):
        api.scan_installed_skills()

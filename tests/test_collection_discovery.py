import pytest

from crucible import api


@pytest.fixture
def root(tmp_path, monkeypatch):
    root = tmp_path / 'skills'
    root.mkdir()
    monkeypatch.setattr(api, '_standard_skill_dirs', lambda: [root])
    return root


def test_unrelated_files_consume_collection_discovery_budget(root, monkeypatch):
    for name in ('a', 'b', 'c'):
        (root / name).touch()
    monkeypatch.setattr(api, '_MAX_COLLECTION_DISCOVERY_ENTRIES', 2, raising=False)
    with pytest.raises(ValueError, match='discovery entry limit'):
        api.scan_installed_collection()


def test_dangling_root_symlink_is_partial_not_empty(root):
    root.rmdir()
    root.symlink_to(root.parent / 'absent', target_is_directory=True)
    result = api.scan_installed_collection()
    assert result['status'] == 'PARTIAL'
    assert result['coverage']['errors'] == 1


def test_directory_named_skill_is_reported_as_invalid(root):
    (root / 'SKILL.md').mkdir()
    result = api.scan_installed_collection()
    assert result['status'] == 'PARTIAL'
    assert result['coverage']['errors'] == 1


def test_replacement_before_file_open_is_reported(root, monkeypatch):
    path = root / 'SKILL.md'
    text = b'---\nname: safe\ndescription: Example.\n---\n'
    path.write_bytes(text)
    original = api.compile_skill_file

    def swap(path, **kwargs):
        path.rename(root / 'saved')
        path.write_bytes(text.replace(b'safe', b'evil'))
        return original(path, **kwargs)

    monkeypatch.setattr(api, 'compile_skill_file', swap)
    result = api.scan_installed_collection()
    assert result['status'] == 'PARTIAL'
    assert result['coverage']['analyzed'] == 0


def test_directory_replacement_preserves_valid_neighbor(root, monkeypatch):
    for name in ('bad', 'good'):
        package = root / name
        package.mkdir()
        (package / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Example.\n---\n')
    original = api._scan_corpus_directory

    def swap(path, **kwargs):
        if path == root / 'bad':
            path.rename(root.parent / 'saved')
            path.mkdir()
            (path / 'SKILL.md').write_text('---\nname: hostile\ndescription: Example.\n---\n')
        return original(path, **kwargs)

    monkeypatch.setattr(api, '_scan_corpus_directory', swap)
    result = api.scan_installed_collection()
    assert result['status'] == 'PARTIAL'
    assert result['coverage'] == {'discovered': 2, 'analyzed': 1, 'errors': 1}
    assert [e['skill_name'] for e in result['entries'] if e['status'] == 'ANALYZED'] == ['good']


def test_entry_budget_is_shared_across_roots(root, monkeypatch):
    other = root.parent / 'other'
    other.mkdir()
    for directory in (root, other):
        for name in ('a', 'b'):
            (directory / name).touch()
    monkeypatch.setattr(api, '_standard_skill_dirs', lambda: [root, other])
    monkeypatch.setattr(api, '_MAX_COLLECTION_DISCOVERY_ENTRIES', 4)
    assert api.scan_installed_collection()['status'] == 'EMPTY'
    monkeypatch.setattr(api, '_MAX_COLLECTION_DISCOVERY_ENTRIES', 3)
    with pytest.raises(ValueError, match='discovery entry limit'):
        api.scan_installed_collection()


def test_listing_stops_on_first_excess_entry(root, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace

    consumed = []

    def children():
        for name in ('a', 'b', 'c'):
            consumed.append(name)
            yield SimpleNamespace(name=name, is_symlink=lambda: False,
                                  is_dir=lambda **kw: False)
        pytest.fail('consumed entries after budget exhaustion')

    @contextmanager
    def scan(path, **kwargs):
        yield children()

    monkeypatch.setattr(api, '_scan_corpus_directory', scan)
    monkeypatch.setattr(api, '_MAX_COLLECTION_DISCOVERY_ENTRIES', 2)
    with pytest.raises(ValueError, match='discovery entry limit'):
        api.scan_installed_collection()
    assert consumed == ['a', 'b', 'c']


def test_directory_permission_failure_is_reported(root, monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def denied(path, **kwargs):
        raise PermissionError('injected permission failure')
        yield

    monkeypatch.setattr(api, '_scan_corpus_directory', denied)
    result = api.scan_installed_collection()
    assert result['status'] == 'PARTIAL'
    assert result['coverage']['errors'] == 1

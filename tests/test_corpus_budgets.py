import pytest

from crucible import compiler


TEXT = b'---\nname: safe\ndescription: Example.\n---\n'


def test_corpus_aggregate_bytes_exact_boundary(tmp_path, monkeypatch):
    (tmp_path / 'SKILL.md').write_bytes(TEXT)
    monkeypatch.setattr(compiler, '_MAX_CORPUS_BYTES', len(TEXT), raising=False)
    assert compiler.compile_corpus(tmp_path)['skills'][0]['identity']['name'] == 'safe'
    monkeypatch.setattr(compiler, '_MAX_CORPUS_BYTES', len(TEXT) - 1)
    with pytest.raises(ValueError, match='byte limit'):
        compiler.compile_corpus(tmp_path)


def test_corpus_bytes_are_shared_across_files(tmp_path, monkeypatch):
    for name in ('one', 'two'):
        package = tmp_path / name
        package.mkdir()
        (package / 'SKILL.md').write_bytes(TEXT.replace(b'safe', name.encode()))
    monkeypatch.setattr(compiler, '_MAX_CORPUS_BYTES', len(TEXT), raising=False)
    with pytest.raises(ValueError, match='byte limit'):
        compiler.compile_corpus(tmp_path)


def test_corpus_empty_directories_consume_budget(tmp_path, monkeypatch):
    (tmp_path / 'SKILL.md').write_bytes(TEXT)
    (tmp_path / 'empty').mkdir()
    monkeypatch.setattr(compiler, '_MAX_CORPUS_DIRECTORIES', 1, raising=False)
    with pytest.raises(ValueError, match='directory limit'):
        compiler.compile_corpus(tmp_path)


def test_corpus_unrelated_files_consume_entry_budget(tmp_path, monkeypatch):
    (tmp_path / 'SKILL.md').write_bytes(TEXT)
    (tmp_path / 'unrelated').touch()
    monkeypatch.setattr(compiler, '_MAX_CORPUS_ENTRIES', 1, raising=False)
    with pytest.raises(ValueError, match='entry limit'):
        compiler.compile_corpus(tmp_path)


def test_corpus_discovery_permission_errors_are_not_silenced(tmp_path, monkeypatch):
    import os

    (tmp_path / 'SKILL.md').write_bytes(TEXT)
    original = os.scandir
    root_stat = tmp_path.stat()

    def denied(path):
        observed = os.fstat(path) if isinstance(path, int) else os.stat(path)
        if (observed.st_dev, observed.st_ino) == (root_stat.st_dev, root_stat.st_ino):
            raise PermissionError('denied for test')
        return original(path)

    monkeypatch.setattr(os, 'scandir', denied)
    with pytest.raises(PermissionError, match='denied for test'):
        compiler.compile_corpus(tmp_path)


def test_discovery_stops_consuming_at_first_excess_entry(tmp_path, monkeypatch):
    import os

    for index in range(10):
        (tmp_path / str(index)).touch()
    original = os.scandir
    consumed = []

    class GuardedScan:
        def __enter__(self):
            self.scan = original(tmp_path)
            return self

        def __exit__(self, *args):
            self.scan.close()

        def __iter__(self):
            return self

        def __next__(self):
            if len(consumed) >= 3:
                pytest.fail('enumerated beyond first excess entry')
            entry = next(self.scan)
            consumed.append(entry.name)
            return entry

    monkeypatch.setattr(os, 'scandir', lambda path: GuardedScan())
    monkeypatch.setattr(compiler, '_MAX_CORPUS_ENTRIES', 2)
    with pytest.raises(ValueError, match='entry limit'):
        compiler.compile_corpus(tmp_path)
    assert len(consumed) == 3


def test_exact_discovery_budgets_allow_nested_skill(tmp_path, monkeypatch):
    package = tmp_path / 'nested'
    package.mkdir()
    (package / 'SKILL.md').write_bytes(TEXT)
    monkeypatch.setattr(compiler, '_MAX_CORPUS_DIRECTORIES', 2)
    monkeypatch.setattr(compiler, '_MAX_CORPUS_ENTRIES', 2)
    result = compiler.compile_corpus(tmp_path, max_skills=1)
    assert result['skills'][0]['identity']['source_path'] == 'nested/SKILL.md'


def test_child_permission_error_does_not_publish_partial_corpus(tmp_path, monkeypatch):
    import os

    (tmp_path / 'SKILL.md').write_bytes(TEXT)
    hidden = tmp_path / 'unreadable'
    hidden.mkdir()
    original = os.scandir
    hidden_stat = hidden.stat()

    def denied(path):
        observed = os.fstat(path) if isinstance(path, int) else os.stat(path)
        if (observed.st_dev, observed.st_ino) == (hidden_stat.st_dev, hidden_stat.st_ino):
            raise PermissionError('subtree denied')
        return original(path)

    monkeypatch.setattr(os, 'scandir', denied)
    with pytest.raises(PermissionError, match='subtree denied'):
        compiler.compile_corpus(tmp_path)

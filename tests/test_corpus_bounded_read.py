import os
from pathlib import Path

import pytest

from crucible.compiler import compile_corpus, compile_skill_file


TEXT = b'---\nname: safe\ndescription: Example.\n---\n1. Validate input.\n'


def test_corpus_rejects_oversized_file_before_read(tmp_path, monkeypatch):
    (tmp_path / 'SKILL.md').write_bytes(TEXT + b'x' * 1_000_000)
    monkeypatch.setattr(Path, 'read_bytes', lambda *a: pytest.fail('unbounded read'))
    monkeypatch.setattr(os, 'read', lambda *a: pytest.fail('oversized read'))
    with pytest.raises(ValueError, match='byte limit'):
        compile_corpus(tmp_path)


def test_corpus_fifo_is_rejected_before_read(tmp_path, monkeypatch):
    os.mkfifo(tmp_path / 'SKILL.md')
    monkeypatch.setattr(Path, 'read_bytes', lambda *a: pytest.fail('FIFO read attempted'))
    monkeypatch.setattr(os, 'read', lambda *a: pytest.fail('FIFO read attempted'))
    with pytest.raises(ValueError, match='regular file'):
        compile_corpus(tmp_path)


def test_corpus_rejects_growth_during_read(tmp_path, monkeypatch):
    path = tmp_path / 'SKILL.md'
    path.write_bytes(TEXT)
    original = os.read

    def grow(fd, count):
        with path.open('ab') as stream:
            stream.write(b'changed')
        return original(fd, count)

    monkeypatch.setattr(os, 'read', grow)
    with pytest.raises(ValueError, match='changed during'):
        compile_corpus(tmp_path)


def test_corpus_reader_preserves_relative_source_and_content(tmp_path):
    package = tmp_path / 'nested' / 'safe'
    package.mkdir(parents=True)
    path = package / 'SKILL.md'
    path.write_bytes(TEXT)
    corpus_skill = compile_corpus(tmp_path)['skills'][0]
    single_skill = compile_skill_file(path)['skills'][0]
    assert corpus_skill['identity']['source_path'] == 'nested/safe/SKILL.md'
    single_skill['identity']['source_path'] = 'nested/safe/SKILL.md'
    assert corpus_skill == single_skill


def test_corpus_rejects_symlink_swap_after_precheck(tmp_path, monkeypatch):
    root = tmp_path / 'corpus'
    root.mkdir()
    path = root / 'SKILL.md'
    path.write_bytes(TEXT)
    external = tmp_path / 'external.md'
    external.write_bytes(TEXT.replace(b'name: safe', b'name: hostile'))
    original = Path.is_symlink

    def swap_after_check(candidate):
        result = original(candidate)
        if candidate == path and not result:
            path.unlink()
            path.symlink_to(external)
        return result

    monkeypatch.setattr(Path, 'is_symlink', swap_after_check)
    with pytest.raises(OSError):
        compile_corpus(root)


def test_corpus_accepts_exact_byte_limit(tmp_path):
    (tmp_path / 'SKILL.md').write_bytes(TEXT + b' ' * (1_000_000 - len(TEXT)))
    assert compile_corpus(tmp_path)['skills'][0]['identity']['name'] == 'safe'

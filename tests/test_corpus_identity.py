import os

import pytest

from crucible import compiler


TEXT = b'---\nname: safe\ndescription: Example.\n---\n'


@pytest.mark.parametrize('replacement', ['parent', 'file', 'root'])
def test_replacement_after_discovery_is_rejected(tmp_path, monkeypatch, replacement):
    root = tmp_path / 'root'
    package = root / 'package'
    package.mkdir(parents=True)
    path = package / 'SKILL.md'
    path.write_bytes(TEXT)
    original = compiler._discover_corpus

    def swap(*args, **kwargs):
        result = original(*args, **kwargs)
        target = {'parent': package, 'file': path, 'root': root}[replacement]
        target.rename(tmp_path / 'saved')
        if replacement != 'file':
            package.mkdir(parents=True)
        path.write_bytes(TEXT.replace(b'name: safe', b'name: hostile'))
        return result

    monkeypatch.setattr(compiler, '_discover_corpus', swap)
    with pytest.raises(ValueError, match='identity changed'):
        compiler.compile_corpus(root)


def test_queued_directory_identity_is_checked(tmp_path, monkeypatch):
    child = tmp_path / 'child'
    child.mkdir()
    (child / 'SKILL.md').write_bytes(TEXT)
    original = compiler._scan_corpus_directory

    def swap(path, *args, **kwargs):
        if path == child:
            child.rename(tmp_path / 'saved')
            child.mkdir()
            (child / 'SKILL.md').write_bytes(TEXT.replace(b'safe', b'hostile'))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(compiler, '_scan_corpus_directory', swap)
    with pytest.raises(ValueError, match='identity changed'):
        compiler.compile_corpus(tmp_path)


def test_file_replacement_at_open_is_checked_before_read(tmp_path, monkeypatch):
    path = tmp_path / 'SKILL.md'
    path.write_bytes(TEXT)
    original = os.open
    opened = []

    def swap(name, flags, *args, **kwargs):
        if name == 'SKILL.md':
            path.rename(tmp_path / 'saved')
            path.write_bytes(TEXT.replace(b'safe', b'hostile'))
        fd = original(name, flags, *args, **kwargs)
        opened.append(fd)
        return fd

    monkeypatch.setattr(os, 'open', swap)
    monkeypatch.setattr(os, 'read', lambda *a: pytest.fail('replacement was read'))
    with pytest.raises(ValueError, match='identity changed'):
        compiler.compile_corpus(tmp_path)
    for fd in opened:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_parent_replacement_rejected_even_when_file_inode_is_unchanged(tmp_path, monkeypatch):
    package = tmp_path / 'package'
    package.mkdir()
    path = package / 'SKILL.md'
    path.write_bytes(TEXT)
    original = compiler._discover_corpus

    def swap(*args, **kwargs):
        paths = original(*args, **kwargs)
        package.rename(tmp_path / 'saved')
        package.mkdir()
        os.link(tmp_path / 'saved' / 'SKILL.md', path)
        return paths

    monkeypatch.setattr(compiler, '_discover_corpus', swap)
    with pytest.raises(ValueError, match='identity changed'):
        compiler.compile_corpus(tmp_path)


def test_identity_metadata_does_not_change_canonical_artifact(tmp_path):
    roots = [tmp_path / 'first', tmp_path / 'second']
    for root in roots:
        root.mkdir()
        (root / 'SKILL.md').write_bytes(TEXT)
    assert compiler.compile_corpus(roots[0]) == compiler.compile_corpus(roots[1])

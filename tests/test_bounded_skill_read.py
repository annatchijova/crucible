import os
from pathlib import Path

import pytest

from crucible.compiler import compile_skill_file


TEXT = b'---\nname: safe\ndescription: Example.\n---\n1. Validate input.\n'


def test_exact_read_limit(tmp_path):
    path = tmp_path / 'SKILL.md'
    path.write_bytes(TEXT)
    assert compile_skill_file(path, len(TEXT))['skills'][0]['identity']['name'] == 'safe'
    with pytest.raises(ValueError, match='byte limit'):
        compile_skill_file(path, len(TEXT) - 1)


def test_growth_during_read_is_rejected_and_bounded(tmp_path, monkeypatch):
    path = tmp_path / 'SKILL.md'
    path.write_bytes(TEXT)
    original = os.read
    consumed = []
    def grow(fd, count):
        with path.open('ab') as stream:
            stream.write(b'x' * 10000)
        chunk = original(fd, count)
        consumed.append(len(chunk))
        return chunk
    monkeypatch.setattr(os, 'read', grow)
    with pytest.raises(ValueError, match='changed during'):
        compile_skill_file(path, len(TEXT))
    assert sum(consumed) <= len(TEXT)


def test_replacement_with_symlink_at_open_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / 'SKILL.md'
    path.write_bytes(TEXT)
    target = tmp_path / 'external'
    target.write_bytes(TEXT)
    original = os.open
    def swap(name, flags, *args, **kwargs):
        if Path(name).name == 'SKILL.md':
            path.unlink()
            path.symlink_to(target)
        return original(name, flags, *args, **kwargs)
    monkeypatch.setattr(os, 'open', swap)
    with pytest.raises(OSError):
        compile_skill_file(path)


def test_fifo_never_reaches_read(tmp_path, monkeypatch):
    path = tmp_path / 'SKILL.md'
    os.mkfifo(path)
    monkeypatch.setattr(os, 'read', lambda *args: pytest.fail('FIFO read attempted'))
    with pytest.raises(ValueError, match='regular file'):
        compile_skill_file(path)


def test_symlinked_ancestor_is_rejected(tmp_path):
    real = tmp_path / 'real'
    real.mkdir()
    (real / 'SKILL.md').write_bytes(TEXT)
    (tmp_path / 'alias').symlink_to(real, target_is_directory=True)
    with pytest.raises(OSError):
        compile_skill_file(tmp_path / 'alias/SKILL.md')


def test_parent_replacement_cannot_redirect_open_descriptor(tmp_path, monkeypatch):
    package = tmp_path / 'package'
    package.mkdir()
    (package / 'SKILL.md').write_bytes(TEXT)
    external = tmp_path / 'external'
    external.mkdir()
    (external / 'SKILL.md').write_bytes(TEXT.replace(b'name: safe', b'name: hostile'))
    original = os.open
    def replace_parent(name, flags, *args, **kwargs):
        if Path(name).name == 'SKILL.md':
            package.rename(tmp_path / 'original-package')
            package.symlink_to(external, target_is_directory=True)
        return original(name, flags, *args, **kwargs)
    monkeypatch.setattr(os, 'open', replace_parent)
    result = compile_skill_file(package / 'SKILL.md')
    assert result['skills'][0]['identity']['name'] == 'safe'

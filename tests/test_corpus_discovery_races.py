import os
import pytest

from crucible import compiler


def test_directory_swap_at_scandir_cannot_enumerate_external_tree(tmp_path, monkeypatch):
    root = tmp_path / 'root'
    root.mkdir()
    (root / 'original').mkdir()
    external = tmp_path / 'external'
    external.mkdir()
    (external / 'SKILL.md').write_text('external content')
    original = os.scandir
    swapped = False

    def swap(path):
        nonlocal swapped
        if not swapped:
            root.rename(tmp_path / 'pinned-root')
            root.symlink_to(external, target_is_directory=True)
            swapped = True
        return original(path)

    monkeypatch.setattr(os, 'scandir', swap)
    # Either reject the changed path or enumerate the pinned original tree.
    try:
        paths = compiler._discover_corpus(root, None)
    except OSError:
        return
    assert paths == [], 'discovery enumerated the external symlink target'


def test_scandir_receives_pinned_descriptor_and_closes_it(tmp_path, monkeypatch):
    original = os.scandir
    descriptors = []

    def track(fd):
        assert isinstance(fd, int), 'discovery reopened a path'
        descriptors.append(fd)
        return original(fd)

    monkeypatch.setattr(os, 'scandir', track)
    assert compiler._discover_corpus(tmp_path, None) == []
    assert descriptors
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_discovery_closes_descriptor_on_enumeration_error(tmp_path, monkeypatch):
    descriptors = []

    def denied(fd):
        assert isinstance(fd, int)
        descriptors.append(fd)
        raise PermissionError('injected')

    monkeypatch.setattr(os, 'scandir', denied)
    with pytest.raises(PermissionError, match='injected'):
        compiler._discover_corpus(tmp_path, None)
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_queued_child_replaced_with_symlink_is_rejected(tmp_path, monkeypatch):
    root = tmp_path / 'root'
    root.mkdir()
    child = root / 'child'
    child.mkdir()
    external = tmp_path / 'external'
    external.mkdir()
    (external / 'SKILL.md').touch()
    original = compiler._scan_corpus_directory

    def swap(path, **kwargs):
        if path == child:
            child.rename(tmp_path / 'saved-child')
            child.symlink_to(external, target_is_directory=True)
        return original(path, **kwargs)

    monkeypatch.setattr(compiler, '_scan_corpus_directory', swap)
    with pytest.raises(OSError):
        compiler._discover_corpus(root, None)


def test_discovery_closes_descriptor_on_budget_failure(tmp_path, monkeypatch):
    (tmp_path / 'SKILL.md').touch()
    original = os.scandir
    descriptors = []

    def track(fd):
        descriptors.append(fd)
        return original(fd)

    monkeypatch.setattr(os, 'scandir', track)
    monkeypatch.setattr(compiler, '_MAX_CORPUS_ENTRIES', 0)
    with pytest.raises(ValueError, match='entry limit'):
        compiler._discover_corpus(tmp_path, None)
    assert descriptors
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)

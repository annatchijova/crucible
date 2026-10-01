import pytest

from crucible import api


TEXT = b'---\nname: safe\ndescription: Example.\n---\n'


@pytest.mark.parametrize('target_name', ['package', 'root'])
@pytest.mark.parametrize('symlink', [False, True])
def test_replacement_after_listing_is_rejected(tmp_path, monkeypatch, target_name, symlink):
    root = tmp_path / 'skills'
    package = root / 'safe'
    package.mkdir(parents=True)
    (package / 'SKILL.md').write_bytes(TEXT)
    monkeypatch.setattr(api, '_find_installed_skill_dirs', lambda: [root])
    original = api._installed_children

    def swap(*args, **kwargs):
        paths = original(*args, **kwargs)
        target = package if target_name == 'package' else root
        target.rename(tmp_path / 'saved')
        if symlink:
            external = tmp_path / 'external'
            external.mkdir()
            target.symlink_to(external, target_is_directory=True)
        package.mkdir(parents=True, exist_ok=True)
        (package / 'SKILL.md').write_bytes(TEXT.replace(b'safe', b'hostile'))
        return paths

    monkeypatch.setattr(api, '_installed_children', swap)
    if symlink:
        with pytest.raises(OSError):
            api.scan_installed_skills()
    else:
        with pytest.raises(ValueError, match='identity changed'):
            api.scan_installed_skills()

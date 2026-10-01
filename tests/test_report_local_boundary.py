import json

import pytest

from crucible import report
from crucible.behavioral import LocalExecutor


@pytest.mark.parametrize('through_cli', [False, True])
def test_explicit_local_report_never_selects_remote_confirmation(
    tmp_path, monkeypatch, capsys, through_cli
):
    (tmp_path / 'SKILL.md').write_text(
        '---\nname: retry\ndescription: Retry operations.\n---\n'
        'Retry MUST continue until success.\n', encoding='utf-8',
    )
    monkeypatch.setenv('NEBIUS_API_KEY', 'dummy-not-a-credential')

    def forbidden():
        pytest.fail('explicit local report selected remote confirmation')

    monkeypatch.setattr(report, 'NebiusConfirmExecutor', forbidden)
    if through_cli:
        from crucible.cli import main
        monkeypatch.setattr('sys.argv', ['crucible', str(tmp_path), '--report', '--local-executor'])
        assert main() == 0
        result = json.loads(capsys.readouterr().out)
    else:
        result = report.run_full_report(str(tmp_path), executor=LocalExecutor())
    assert result['levels']['L2.5']['executor_model'] == report.MockConfirmExecutor().model

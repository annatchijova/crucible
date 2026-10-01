"""Replay CLI privacy, offline authority and exit-code contracts."""
import io
import json
import sys

import pytest

from crucible import cli
from crucible.behavioral import NebiusExecutor
from crucible.capture_bundle import capture_behavioral_bundle
from crucible.capture_journal import CaptureJournal, read_journal
from crucible.replay import load_bundle


def invoke(monkeypatch, *args):
    monkeypatch.setattr(sys, 'argv', ['crucible', *map(str, args)])
    return cli.main()


@pytest.fixture
def no_network(monkeypatch):
    monkeypatch.delenv('NEBIUS_API_KEY', raising=False)
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', lambda *a, **k: pytest.fail('network'))


def test_blocked_capture_inspect_and_export(tmp_path, monkeypatch, capsys, no_network):
    path = tmp_path / 'journal'
    assert invoke(monkeypatch, '--capture-replay', path) == 1
    summary = json.loads(capsys.readouterr().out)
    assert summary['schema_version'] == 'crucible-replay-cli/v1'
    assert summary['status'] == 'COMPLETE'
    assert summary['captured_variants'] == 4
    assert summary['evidence_complete'] is False
    assert 'captures' not in summary and 'bundle' not in summary
    monkeypatch.setenv('NEBIUS_API_KEY', 'dummy-present-but-offline')
    monkeypatch.setattr('crucible.behavioral.NebiusExecutor', lambda: pytest.fail('executor constructed'))
    assert invoke(monkeypatch, '--inspect-replay', path) == 1
    assert json.loads(capsys.readouterr().out) == summary
    assert invoke(monkeypatch, '--export-replay', path) == 1
    output = capsys.readouterr()
    bundle = load_bundle(output.out)
    assert bundle == read_journal(path)['bundle']
    assert 'private' in output.err.lower()


def test_complete_capture_returns_zero_but_not_acceptance(tmp_path, monkeypatch, capsys):
    payload = {'id': 'fixture', 'choices': [{'message': {'content': 'private-output-marker'},
                                          'finish_reason': 'stop'}],
               'usage': {'prompt_tokens': 1, 'completion_tokens': 2, 'total_tokens': 3}}
    class Response(io.BytesIO):
        def getcode(self):
            return 200
    monkeypatch.setenv('NEBIUS_API_KEY', 'dummy')
    calls = []
    def opener(*args, **kwargs):
        calls.append(1)
        return Response(json.dumps(payload).encode())
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', opener)
    path = tmp_path / 'complete'
    assert invoke(monkeypatch, '--capture-replay', path) == 0
    output = capsys.readouterr()
    assert len(calls) == 4
    assert 'private-output-marker' not in output.out + output.err
    summary = json.loads(output.out)
    assert summary['evidence_complete'] is True
    assert 'accepted' not in summary


@pytest.mark.parametrize('mode', ['--inspect-replay', '--export-replay'])
def test_partial_journal_is_not_promoted(tmp_path, monkeypatch, capsys, no_network, mode):
    executor = NebiusExecutor()
    class Interrupted:
        calls = 0
        def capture_exchange(self, system_prompt, user_prompt):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError('stop')
            return executor.capture_exchange(system_prompt, user_prompt)
    path = tmp_path / 'partial'
    with CaptureJournal(path) as journal, pytest.raises(RuntimeError):
        capture_behavioral_bundle(Interrupted(), journal=journal)
    assert invoke(monkeypatch, mode, path) == 1
    output = capsys.readouterr()
    if mode == '--inspect-replay':
        summary = json.loads(output.out)
        assert summary['status'] == 'PARTIAL' and summary['captured_variants'] == 1
        assert len(summary['pending_variants']) == 3
    else:
        assert output.out == ''
        assert 'partial' in output.err.lower()


@pytest.mark.parametrize('extra', [
    ['--behave'], ['--report'], ['--local-executor'], ['--scan-installed'],
    ['--view', 'artifact.json'], ['corpus'], ['--serve'], ['--compile-only'],
    ['--inspect-replay', 'another'], ['--mock-confirm'], ['--include-coverage'],
])
def test_conflicting_modes_fail_before_side_effects(tmp_path, monkeypatch, no_network, extra):
    path = tmp_path / 'not-created'
    with pytest.raises(SystemExit) as exc:
        invoke(monkeypatch, '--capture-replay', path, *extra)
    assert exc.value.code == 2
    assert not path.exists()


def test_existing_destination_fails_before_provider(tmp_path, monkeypatch, capsys, no_network):
    path = tmp_path / 'existing'
    path.mkdir()
    assert invoke(monkeypatch, '--capture-replay', path) == 2
    assert capsys.readouterr().out == ''
    assert list(path.iterdir()) == []


@pytest.mark.parametrize('mode', ['--inspect-replay', '--export-replay'])
def test_missing_journal_does_not_create_it(tmp_path, monkeypatch, capsys, no_network, mode):
    path = tmp_path / 'missing'
    assert invoke(monkeypatch, mode, path) == 2
    output = capsys.readouterr()
    assert output.out == '' and output.err
    assert not path.exists()


def test_capture_interrupt_retains_journal_and_hides_exception(tmp_path, monkeypatch, capsys, no_network):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt('secret exception text')
    monkeypatch.setattr('crucible.behavioral.NebiusExecutor.capture_exchange', interrupted)
    path = tmp_path / 'interrupt'
    assert invoke(monkeypatch, '--capture-replay', path) == 130
    output = capsys.readouterr()
    assert 'secret exception text' not in output.out + output.err
    assert read_journal(path)['status'] == 'PARTIAL'


def test_unexpected_capture_error_is_sanitized(tmp_path, monkeypatch, capsys, no_network):
    def fail(*args, **kwargs):
        raise RuntimeError('credential-must-not-appear')
    monkeypatch.setattr('crucible.behavioral.NebiusExecutor.capture_exchange', fail)
    path = tmp_path / 'failed'
    assert invoke(monkeypatch, '--capture-replay', path) == 2
    output = capsys.readouterr()
    assert output.out == ''
    assert 'credential-must-not-appear' not in output.err
    assert read_journal(path)['status'] == 'PARTIAL'


@pytest.mark.parametrize('finish', ['length', None])
def test_truncated_or_missing_finish_exports_without_success(tmp_path, monkeypatch, capsys, finish):
    payload = {'id': 'fake', 'choices': [{'message': {'content': 'bounded retries'},
                                       'finish_reason': finish}],
               'usage': {'prompt_tokens': 1, 'completion_tokens': 2, 'total_tokens': 3}}
    class Response(io.BytesIO):
        def getcode(self):
            return 200
    monkeypatch.setenv('NEBIUS_API_KEY', 'dummy')
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', lambda *a, **k: Response(json.dumps(payload).encode()))
    path = tmp_path / 'incomplete'
    assert invoke(monkeypatch, '--capture-replay', path) == 1
    assert json.loads(capsys.readouterr().out)['evidence_complete'] is False
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', lambda *a, **k: pytest.fail('network'))
    assert invoke(monkeypatch, '--export-replay', path) == 1
    assert load_bundle(capsys.readouterr().out) == read_journal(path)['bundle']


def test_empty_journal_is_inspectable_but_not_exportable(tmp_path, monkeypatch, capsys, no_network):
    path = tmp_path / 'empty'
    with CaptureJournal(path):
        pass
    assert invoke(monkeypatch, '--inspect-replay', path) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'EMPTY'
    assert invoke(monkeypatch, '--export-replay', path) == 1
    assert capsys.readouterr().out == ''


def test_corrupted_journal_never_exports_a_bundle(tmp_path, monkeypatch, capsys, no_network):
    path = tmp_path / 'corrupted'
    with CaptureJournal(path) as journal:
        capture_behavioral_bundle(NebiusExecutor(), journal=journal)
        journal.connection.execute("UPDATE experiment SET digest='wrong'")
    assert invoke(monkeypatch, '--export-replay', path) == 2
    assert capsys.readouterr().out == ''

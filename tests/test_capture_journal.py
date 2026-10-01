"""Private, incremental capture retention without provider retries."""
import os
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from crucible.behavioral import NebiusExecutor
from crucible.capture_bundle import capture_behavioral_bundle


def blocked(monkeypatch):
    monkeypatch.delenv('NEBIUS_API_KEY', raising=False)
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', lambda *a, **k: pytest.fail('network'))
    return NebiusExecutor()


def test_completed_journal_roundtrip_and_private_permissions(tmp_path, monkeypatch):
    from crucible.capture_journal import CaptureJournal, read_journal
    executor = blocked(monkeypatch)
    path = tmp_path / 'experiment'
    with CaptureJournal(path) as journal:
        bundle = capture_behavioral_bundle(executor, journal=journal)
        snapshot = read_journal(path)
        assert snapshot['status'] == 'COMPLETE'
        assert snapshot['bundle'] == bundle
        assert not snapshot['pending_variants']
    assert read_journal(path)['bundle'] == bundle
    assert path.stat().st_mode & 0o777 == 0o700
    assert (path / 'evidence.sqlite3').stat().st_mode & 0o777 == 0o600
    # COMPLETE means acquisition finished, not that blocked evidence is ready.
    from crucible.replay import replay_readiness
    assert not replay_readiness(bundle)['evidence_complete']


def test_existing_destination_never_overwritten(tmp_path):
    from crucible.capture_journal import CaptureJournal
    path = tmp_path / 'existing'
    path.mkdir()
    marker = path / 'keep'
    marker.write_text('user data')
    with pytest.raises(FileExistsError):
        CaptureJournal(path)
    assert marker.read_text() == 'user data'


def test_failure_on_second_variant_preserves_first_capture(tmp_path, monkeypatch):
    from crucible.capture_journal import CaptureJournal, read_journal
    executor = blocked(monkeypatch)
    class InterruptingExecutor:
        calls = 0
        def capture_exchange(self, system_prompt, user_prompt):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError('interrupted')
            return executor.capture_exchange(system_prompt, user_prompt)
    path = tmp_path / 'partial'
    with CaptureJournal(path) as journal, pytest.raises(RuntimeError, match='interrupted'):
        capture_behavioral_bundle(InterruptingExecutor(), journal=journal)
    snapshot = read_journal(path)
    assert snapshot['status'] == 'PARTIAL'
    assert snapshot['bundle'] is None
    assert len(snapshot['captures']) == 1
    assert len(snapshot['pending_variants']) == 3


def test_capture_commits_before_projection(tmp_path, monkeypatch):
    from crucible.capture_journal import CaptureJournal, read_journal
    executor = blocked(monkeypatch)
    monkeypatch.setattr('crucible.capture_bundle.capture_projection', lambda *a: (_ for _ in ()).throw(RuntimeError('projection crash')))
    path = tmp_path / 'raw-first'
    with CaptureJournal(path) as journal, pytest.raises(RuntimeError, match='projection crash'):
        capture_behavioral_bundle(executor, journal=journal)
    snapshot = read_journal(path)
    assert len(snapshot['captures']) == 1
    assert snapshot['captures'][0]['observations'] is None
    assert snapshot['status'] == 'PARTIAL'
    assert snapshot['unobserved_variants'] == ['V1-no-skill']


def test_process_exit_without_close_retains_committed_capture(tmp_path):
    from crucible.capture_journal import read_journal
    path = tmp_path / 'crashed'
    script = '''
import os, sys
from crucible.behavioral import NebiusExecutor
from crucible.capture_bundle import capture_behavioral_bundle
from crucible.capture_journal import CaptureJournal
os.environ.pop('NEBIUS_API_KEY', None)
class Executor:
    calls = 0
    def capture_exchange(self, system_prompt, user_prompt):
        self.calls += 1
        if self.calls == 2:
            os._exit(17)
        return NebiusExecutor().capture_exchange(system_prompt, user_prompt)
with CaptureJournal(sys.argv[1]) as journal:
    capture_behavioral_bundle(Executor(), journal=journal)
'''
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
    result = subprocess.run([sys.executable, '-c', script, str(path)], env=env, timeout=10)
    assert result.returncode == 17
    snapshot = read_journal(path)
    assert snapshot['status'] == 'PARTIAL'
    assert len(snapshot['captures']) == 1


def test_failed_completion_transaction_rolls_back(tmp_path, monkeypatch):
    from crucible.capture_journal import CaptureJournal, read_journal
    executor = blocked(monkeypatch)
    path = tmp_path / 'rollback'
    with CaptureJournal(path) as journal:
        journal.connection.execute("CREATE TRIGGER fail_finish BEFORE UPDATE OF bundle ON experiment BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with pytest.raises(sqlite3.IntegrityError, match='injected'):
            capture_behavioral_bundle(executor, journal=journal)
        snapshot = read_journal(path)
        assert snapshot['status'] == 'PARTIAL'
        assert len(snapshot['captures']) == 4
        assert snapshot['bundle'] is None


def test_unknown_journal_version_is_rejected(tmp_path):
    from crucible.capture_journal import CaptureJournal, read_journal
    path = tmp_path / 'version'
    with CaptureJournal(path) as journal:
        journal.connection.execute('PRAGMA user_version = 999')
    with pytest.raises(ValueError, match='version'):
        read_journal(path)


def test_checkpoint_failure_stops_provider_calls(tmp_path, monkeypatch):
    from crucible.capture_journal import CaptureJournal, read_journal
    executor = blocked(monkeypatch)
    class CountingExecutor:
        calls = 0
        def capture_exchange(self, system_prompt, user_prompt):
            self.calls += 1
            return executor.capture_exchange(system_prompt, user_prompt)
    counting = CountingExecutor()
    path = tmp_path / 'write-failure'
    with CaptureJournal(path) as journal:
        journal.connection.execute("CREATE TRIGGER fail_capture BEFORE INSERT ON captures BEGIN SELECT RAISE(ABORT, 'write failure'); END")
        with pytest.raises(sqlite3.IntegrityError, match='write failure'):
            capture_behavioral_bundle(counting, journal=journal)
    assert counting.calls == 1
    snapshot = read_journal(path)
    assert snapshot['status'] == 'PARTIAL'
    assert snapshot['captures'] == []


def test_completed_journal_cannot_be_reused_or_changed(tmp_path, monkeypatch):
    from crucible.capture_journal import CaptureJournal, read_journal
    executor = blocked(monkeypatch)
    path = tmp_path / 'immutable'
    with CaptureJournal(path) as journal:
        bundle = capture_behavioral_bundle(executor, journal=journal)
        run = bundle['runs'][0]
        with pytest.raises(ValueError):
            journal.record_capture(run['variant_id'], run['capture'])
        with pytest.raises(ValueError):
            journal.record_observations(run['variant_id'], [])
        with pytest.raises(ValueError):
            journal.finish(bundle)
        assert read_journal(path)['bundle'] == bundle


def test_changed_evidence_cannot_hide_behind_complete_bundle(tmp_path, monkeypatch):
    from crucible.capture_journal import CaptureJournal, read_journal
    executor = blocked(monkeypatch)
    path = tmp_path / 'corruption'
    with CaptureJournal(path) as journal:
        capture_behavioral_bundle(executor, journal=journal)
        journal.connection.execute("UPDATE captures SET observations='[]', observation_digest='changed' WHERE position=0")
        with pytest.raises(ValueError, match='observations digest'):
            read_journal(path)


def test_text_response_and_observations_survive_reopen(tmp_path, monkeypatch):
    from crucible.capture_journal import CaptureJournal, read_journal
    from crucible.replay import replay_readiness
    payload = {'id': 'fixture', 'choices': [{'message': {'content': 'Use at most 3 attempts.'},
                                          'finish_reason': 'stop'}],
               'usage': {'prompt_tokens': 2, 'completion_tokens': 4, 'total_tokens': 6}}
    class Response(io.BytesIO):
        def getcode(self):
            return 200
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen',
                        lambda *a, **k: Response(json.dumps(payload).encode()))
    path = tmp_path / 'text-response'
    with CaptureJournal(path) as journal:
        bundle = capture_behavioral_bundle(NebiusExecutor(api_key='dummy'), journal=journal)
    recovered = read_journal(path)
    assert recovered['bundle'] == bundle
    assert recovered['captures'] == bundle['runs']
    assert all(len(run['observations']) == 4 for run in recovered['captures'])
    assert replay_readiness(recovered['bundle'])['evidence_complete']

"""Private, opt-in SQLite checkpoints for locally owned capture experiments.

The destination parent and SQLite files are trusted local storage, not an import
format for hostile databases. No resume, retry, migration or acceptance logic.
"""

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3

from .capture_contract import strict_json, validate_capture
from .ir import canonical_bytes, digest_payload
from .replay import CAPTURE_REPLAY_VERSION, _fields, dump_bundle, load_bundle

JOURNAL_VERSION = 'crucible-capture-journal/v1'
MAX_JOURNAL_BYTES = 24_000_000


def _json(value):
    return canonical_bytes(value).decode('utf-8')


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _budget(connection):
    count, size = connection.execute(
        'SELECT COUNT(*), COALESCE(SUM(length(CAST(capture AS BLOB)) + '
        'COALESCE(length(CAST(observations AS BLOB)), 0)), 0) FROM captures'
    ).fetchone()
    size += connection.execute(
        'SELECT COALESCE(SUM(length(CAST(metadata AS BLOB)) + '
        'COALESCE(length(CAST(bundle AS BLOB)), 0)), 0) FROM experiment'
    ).fetchone()[0]
    if count > 500 or size > MAX_JOURNAL_BYTES:
        raise ValueError('journal payload limit exceeded')


class CaptureJournal:
    """Create an exclusive experiment directory; existing paths are never reused."""

    def __init__(self, path):
        if os.name != 'posix':
            raise OSError('private capture journals currently require POSIX')
        self.path = Path(path).absolute()
        self.path.mkdir(mode=0o700)
        database = self.path / 'evidence.sqlite3'
        fd = os.open(database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        self.connection = sqlite3.connect(database, isolation_level=None, timeout=5)
        try:
            self.connection.execute('PRAGMA busy_timeout=5000')
            self.connection.execute('PRAGMA journal_mode=WAL')
            self.connection.execute('PRAGMA synchronous=FULL')
            with self._atomic(check_budget=False):
                self.connection.execute('CREATE TABLE experiment (id INTEGER PRIMARY KEY CHECK(id=1), metadata TEXT NOT NULL, digest TEXT NOT NULL, bundle TEXT)')
                self.connection.execute('CREATE TABLE captures (position INTEGER PRIMARY KEY, variant_id TEXT UNIQUE NOT NULL, capture TEXT NOT NULL, observations TEXT, observation_digest TEXT)')
                self.connection.execute('PRAGMA user_version=1')
            _sync_directory(self.path)
            _sync_directory(self.path.parent)
        except BaseException:
            self.connection.close()
            raise

    @contextmanager
    def _atomic(self, *, check_budget=True):
        # Adapted from atomic-state-mutation's BEGIN IMMEDIATE/rollback pattern.
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            yield
            if check_budget:
                _budget(self.connection)
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def start(self, experiment):
        _fields(experiment, 'schema_version request_adapter task task_digest variants oracle runs', 'experiment')
        if experiment['schema_version'] != CAPTURE_REPLAY_VERSION or experiment['runs'] != []:
            raise ValueError('journal requires a new v2 experiment')
        with self._atomic():
            self.connection.execute('INSERT INTO experiment VALUES (1, ?, ?, NULL)',
                                    (_json(experiment), digest_payload(experiment)))

    def record_capture(self, variant_id, capture):
        capture = validate_capture(capture)
        with self._atomic():
            row = self.connection.execute('SELECT metadata, bundle FROM experiment WHERE id=1').fetchone()
            if row is None or row[1] is not None:
                raise ValueError('journal is not an active experiment')
            experiment = strict_json(row[0])
            position = self.connection.execute('SELECT COUNT(*) FROM captures').fetchone()[0]
            if position >= len(experiment['variants']):
                raise ValueError('all variants already captured')
            variant = experiment['variants'][position]
            if variant_id != variant['variant_id'] or capture['guidance'] != {
                'system_prompt': variant['skill_text'], 'user_prompt': experiment['task']['task_prompt']
            }:
                raise ValueError('journal capture identity mismatch')
            self.connection.execute('INSERT INTO captures VALUES (?, ?, ?, NULL, NULL)',
                                    (position, variant_id, _json(capture)))

    def record_observations(self, variant_id, observations):
        with self._atomic():
            changed = self.connection.execute(
                'UPDATE captures SET observations=?, observation_digest=? '
                'WHERE variant_id=? AND observations IS NULL',
                (_json(observations), digest_payload(observations), variant_id),
            ).rowcount
            if changed != 1:
                raise ValueError('capture missing or observations already recorded')

    def finish(self, bundle):
        text = dump_bundle(bundle)
        with self._atomic():
            snapshot = _snapshot(self.connection)
            if snapshot['status'] != 'PARTIAL':
                raise ValueError('journal is not an active experiment')
            _matches_bundle(snapshot['experiment'], snapshot['captures'], bundle)
            self.connection.execute('UPDATE experiment SET bundle=? WHERE id=1', (text,))

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _matches_bundle(experiment, captures, bundle):
    metadata = {key: value for key, value in bundle.items() if key != 'bundle_digest'}
    metadata['runs'] = []
    if metadata != experiment or bundle['runs'] != captures:
        raise ValueError('bundle does not match journal evidence')


def _snapshot(connection):
    if connection.execute('PRAGMA user_version').fetchone()[0] != 1:
        raise ValueError('unsupported journal version')
    _budget(connection)
    row = connection.execute('SELECT metadata, digest, bundle FROM experiment WHERE id=1').fetchone()
    result = dict(schema_version=JOURNAL_VERSION, status='EMPTY', experiment=None,
                  captures=[], pending_variants=[], unobserved_variants=[], bundle=None)
    if row is None:
        return result
    experiment = strict_json(row[0])
    if digest_payload(experiment) != row[1]:
        raise ValueError('journal metadata digest mismatch')
    _fields(experiment, 'schema_version request_adapter task task_digest variants oracle runs', 'experiment')
    if experiment['schema_version'] != CAPTURE_REPLAY_VERSION or experiment['runs'] != []:
        raise ValueError('unsupported journal experiment')
    captures = []
    for position, variant_id, raw, observations, observation_digest in connection.execute(
        'SELECT position, variant_id, capture, observations, observation_digest FROM captures ORDER BY position'
    ):
        if position != len(captures) or position >= len(experiment['variants']):
            raise ValueError('journal capture sequence mismatch')
        capture = validate_capture(strict_json(raw))
        variant = experiment['variants'][position]
        if variant_id != variant['variant_id'] or capture['guidance'] != {
            'system_prompt': variant['skill_text'], 'user_prompt': experiment['task']['task_prompt']
        }:
            raise ValueError('journal capture identity mismatch')
        observed = None if observations is None else strict_json(observations)
        if (observed is None and observation_digest is not None) or (
            observed is not None and digest_payload(observed) != observation_digest
        ):
            raise ValueError('journal observations digest mismatch')
        captures.append(dict(variant_id=variant_id, capture=capture, observations=observed))
    bundle = None if row[2] is None else load_bundle(row[2])
    if bundle is not None:
        _matches_bundle(experiment, captures, bundle)
    result.update(status='COMPLETE' if bundle is not None else 'PARTIAL',
                  experiment=experiment, captures=captures, bundle=bundle,
                  pending_variants=[v['variant_id'] for v in experiment['variants'][len(captures):]],
                  unobserved_variants=[r['variant_id'] for r in captures if r['observations'] is None])
    return result


def read_journal(path):
    """Read one consistent local checkpoint, without executing a provider/oracle."""
    path = Path(path).absolute()
    database = path / 'evidence.sqlite3'
    if path.is_symlink() or database.is_symlink() or not database.is_file():
        raise ValueError('journal must be an existing local database')
    connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=5,
                                 isolation_level=None)
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('PRAGMA busy_timeout=5000')
        connection.execute('BEGIN')
        return _snapshot(connection)
    finally:
        connection.close()

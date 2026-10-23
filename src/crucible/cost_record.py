"""Non-deterministic execution cost observations, kept out of every decision.

Cost answers a different question from correctness: what does it take to run
the analyzer as a corpus grows. The measurement is inherently irreproducible --
it depends on the machine, its load, the filesystem cache and the interpreter --
so this module is deliberately built so that nothing can gate on it.

Three rules follow from ``CLAUDE.md`` sections 5.2 and 5.3, and the tests
enforce all three:

* **Integers only.** Durations are whole nanoseconds from
  :func:`time.monotonic_ns` and memory is whole kilobytes. No float enters a
  record, so no float can leak into a sealed artifact through one.
* **No derived average.** A mean would reintroduce a float. A series reports
  its minimum, maximum and the integer count of runs, and retains every run.
* **Declared guarantee level.** ``determinism_level`` is always
  ``"observation"``. A record names the corpus and audit it measured, so a
  cost claim cannot be silently attached to different inputs, but agreement
  between two records is never evidence of correctness.

``record_digest`` seals the stored record against later edits. It does not make
the measured numbers reproducible and must never be read as doing so.
"""

import platform
import sys
import time
from copy import deepcopy

from .ir import digest_payload
from .replay import _digest, _fields, _text

COST_RECORD_VERSION = 'cost-record/v1'
DETERMINISM_LEVEL = 'observation'

COST_LIMITATION = (
    'execution cost is a non-deterministic observation of one machine under one '
    'load; it is not reproducible, carries no authority over any finding, '
    'verdict or gate, and agreement between records is not evidence of '
    'correctness'
)

_MAX_RUNS = 1_000
_INTEGER_MEASURES = ('wall_ns', 'peak_rss_kb')
_INTEGER_SCALE = ('skill_count', 'input_bytes', 'finding_count', 'edge_count')


def runtime_context():
    """Describe the measuring environment well enough to discount a comparison."""
    return {
        'python_version': platform.python_version(),
        'platform': platform.platform(),
        'machine': platform.machine(),
        'max_recursion': sys.getrecursionlimit(),
    }


class Stopwatch:
    """Monotonic integer-nanosecond timing. Never use the result as a gate."""

    def __init__(self):
        self._start = None
        self.wall_ns = None

    def __enter__(self):
        self._start = time.monotonic_ns()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.wall_ns = time.monotonic_ns() - self._start
        return False


def build_cost_record(*, corpus_id, corpus_provenance_digest, audit_digest,
                      scale, runs, context=None):
    """Seal a cost series against the corpus and audit it measured."""
    _text(corpus_id, 'corpus_id')
    _digest(corpus_provenance_digest, 'corpus_provenance_digest')
    _digest(audit_digest, 'audit_digest')
    _fields(scale, ' '.join(_INTEGER_SCALE), 'scale')
    for key in _INTEGER_SCALE:
        _whole(scale[key], f'scale {key}')
    observations = [_run(index, run) for index, run in enumerate(runs)]
    if not observations:
        raise ValueError('a cost record needs at least one run')
    if len(observations) > _MAX_RUNS:
        raise ValueError('cost run limit exceeded')
    payload = {
        'schema_version': COST_RECORD_VERSION,
        'determinism_level': DETERMINISM_LEVEL,
        'corpus_id': corpus_id,
        'corpus_provenance_digest': corpus_provenance_digest,
        'audit_digest': audit_digest,
        'scale': {key: scale[key] for key in _INTEGER_SCALE},
        'runs': observations,
        'run_count': len(observations),
        'range': _range(observations),
        'runtime_context': dict(context) if context is not None else runtime_context(),
        'limitation': COST_LIMITATION,
    }
    payload['record_digest'] = digest_payload(payload)
    return payload


def validate_cost_record(record):
    """Check schema, integer discipline and seal, returning an independent copy."""
    if type(record) is not dict or record.get('schema_version') != COST_RECORD_VERSION:
        raise ValueError('unsupported cost record schema version')
    _fields(
        record,
        'schema_version determinism_level corpus_id corpus_provenance_digest '
        'audit_digest scale runs run_count range runtime_context limitation '
        'record_digest',
        'cost record',
    )
    if record['determinism_level'] != DETERMINISM_LEVEL:
        raise ValueError('a cost record may only declare the observation level')
    if record['limitation'] != COST_LIMITATION:
        raise ValueError('cost limitation text was altered')
    _text(record['corpus_id'], 'corpus_id')
    _digest(record['corpus_provenance_digest'], 'corpus_provenance_digest')
    _digest(record['audit_digest'], 'audit_digest')
    _fields(record['scale'], ' '.join(_INTEGER_SCALE), 'scale')
    for key in _INTEGER_SCALE:
        _whole(record['scale'][key], f'scale {key}')
    runs = record['runs']
    if type(runs) is not list or not runs:
        raise ValueError('a cost record needs at least one run')
    if len(runs) > _MAX_RUNS:
        raise ValueError('cost run limit exceeded')
    for index, run in enumerate(runs):
        _fields(run, 'run_index ' + ' '.join(_INTEGER_MEASURES), 'cost run')
        if run['run_index'] != index:
            raise ValueError('cost runs are not contiguously indexed from zero')
        for key in _INTEGER_MEASURES:
            _whole(run[key], f'run {key}')
    if type(record['run_count']) is not int or record['run_count'] != len(runs):
        raise ValueError('run_count does not match the retained runs')
    if record['range'] != _range(runs):
        raise ValueError('cost range does not match the retained runs')
    if type(record['runtime_context']) is not dict:
        raise ValueError('runtime_context: expected object')
    sealed = {key: value for key, value in record.items() if key != 'record_digest'}
    if record['record_digest'] != digest_payload(sealed):
        raise ValueError('cost record digest mismatch')
    return deepcopy(record)


def _run(index, run):
    _fields(run, ' '.join(_INTEGER_MEASURES), 'cost run')
    for key in _INTEGER_MEASURES:
        _whole(run[key], f'run {key}')
    return {'run_index': index, **{key: run[key] for key in _INTEGER_MEASURES}}


def _range(runs):
    """Report extremes only. A mean or median would reintroduce a float."""
    return {
        key: {'min': min(run[key] for run in runs), 'max': max(run[key] for run in runs)}
        for key in _INTEGER_MEASURES
    }


def _whole(value, label):
    """Reject bool before int, and reject any float including an integral one."""
    if type(value) is not int or value < 0:
        raise ValueError(f'{label}: expected a non-negative whole number')

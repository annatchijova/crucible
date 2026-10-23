"""Cost observations stay integer-only, authority-free and bound to their inputs."""
import json
from copy import deepcopy

import pytest

from crucible.cost_record import (
    COST_LIMITATION,
    COST_RECORD_VERSION,
    DETERMINISM_LEVEL,
    Stopwatch,
    build_cost_record,
    runtime_context,
    validate_cost_record,
)
from crucible.ir import canonical_bytes, digest_payload

DIGEST_A = f"sha256:{'a' * 64}"
DIGEST_B = f"sha256:{'b' * 64}"
SCALE = {'skill_count': 818, 'input_bytes': 4_000_000, 'finding_count': 1056, 'edge_count': 0}
RUNS = ({'wall_ns': 3_960_000_000, 'peak_rss_kb': 80_392},
        {'wall_ns': 3_780_000_000, 'peak_rss_kb': 80_100})


def reseal(record):
    record['record_digest'] = digest_payload(
        {k: v for k, v in record.items() if k != 'record_digest'}
    )


@pytest.fixture
def record():
    return build_cost_record(
        corpus_id='mukul975', corpus_provenance_digest=DIGEST_A,
        audit_digest=DIGEST_B, scale=SCALE, runs=RUNS,
        context={'python_version': '3.12.0'},
    )


def test_record_binds_cost_to_the_corpus_and_audit_measured(record):
    assert record['schema_version'] == COST_RECORD_VERSION
    assert record['corpus_provenance_digest'] == DIGEST_A
    assert record['audit_digest'] == DIGEST_B
    assert record['scale'] == SCALE
    assert validate_cost_record(record) == record


def test_record_always_declares_the_observation_level(record):
    assert record['determinism_level'] == DETERMINISM_LEVEL == 'observation'
    assert record['limitation'] == COST_LIMITATION
    assert 'not reproducible' in record['limitation']
    assert 'no authority' in record['limitation']


def test_every_run_is_retained_and_contiguously_indexed(record):
    assert record['run_count'] == len(RUNS) == len(record['runs'])
    assert [run['run_index'] for run in record['runs']] == [0, 1]
    for index, run in enumerate(RUNS):
        assert record['runs'][index]['wall_ns'] == run['wall_ns']


def test_range_reports_extremes_and_never_an_average(record):
    assert record['range']['wall_ns'] == {'min': 3_780_000_000, 'max': 3_960_000_000}
    assert record['range']['peak_rss_kb'] == {'min': 80_100, 'max': 80_392}
    assert set(record['range']['wall_ns']) == {'min', 'max'}
    for measure in record['range'].values():
        assert 'mean' not in measure and 'median' not in measure and 'avg' not in measure


def test_no_float_can_reach_a_cost_record(record):
    def walk(value):
        if type(value) is float:
            raise AssertionError(f'float reached the cost record: {value!r}')
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(record)
    assert b'.' not in canonical_bytes(record['range'])


def test_float_duration_is_refused_even_when_integral():
    with pytest.raises(ValueError, match='expected a non-negative whole number'):
        build_cost_record(
            corpus_id='c', corpus_provenance_digest=DIGEST_A, audit_digest=DIGEST_B,
            scale=SCALE, runs=({'wall_ns': 3.0, 'peak_rss_kb': 1},),
        )


def test_boolean_is_refused_before_integer_coercion():
    with pytest.raises(ValueError, match='expected a non-negative whole number'):
        build_cost_record(
            corpus_id='c', corpus_provenance_digest=DIGEST_A, audit_digest=DIGEST_B,
            scale=SCALE, runs=({'wall_ns': True, 'peak_rss_kb': 1},),
        )


def test_negative_duration_is_refused():
    with pytest.raises(ValueError, match='expected a non-negative whole number'):
        build_cost_record(
            corpus_id='c', corpus_provenance_digest=DIGEST_A, audit_digest=DIGEST_B,
            scale=SCALE, runs=({'wall_ns': -1, 'peak_rss_kb': 1},),
        )


def test_a_record_with_no_runs_is_refused():
    with pytest.raises(ValueError, match='at least one run'):
        build_cost_record(
            corpus_id='c', corpus_provenance_digest=DIGEST_A, audit_digest=DIGEST_B,
            scale=SCALE, runs=(),
        )


def test_unsealed_digest_binding_detects_a_rewritten_corpus_reference(record):
    tampered = deepcopy(record)
    tampered['corpus_provenance_digest'] = DIGEST_B
    with pytest.raises(ValueError, match='cost record digest mismatch'):
        validate_cost_record(tampered)


def test_a_dropped_leading_run_breaks_index_contiguity(record):
    tampered = deepcopy(record)
    del tampered['runs'][0]
    reseal(tampered)
    with pytest.raises(ValueError, match='not contiguously indexed'):
        validate_cost_record(tampered)


def test_a_dropped_slow_run_cannot_be_hidden(record):
    """Dropping the trailing run keeps indices contiguous, so run_count catches it."""
    tampered = deepcopy(record)
    slowest = tampered['range']['wall_ns']['max']
    assert tampered['runs'][0]['wall_ns'] == slowest
    del tampered['runs'][1]
    reseal(tampered)
    with pytest.raises(ValueError, match='run_count does not match'):
        validate_cost_record(tampered)


def test_a_range_narrowed_against_its_runs_is_refused(record):
    tampered = deepcopy(record)
    tampered['range']['wall_ns']['max'] = 1
    reseal(tampered)
    with pytest.raises(ValueError, match='cost range does not match'):
        validate_cost_record(tampered)


def test_an_escalated_determinism_level_is_refused(record):
    tampered = deepcopy(record)
    tampered['determinism_level'] = 'deterministic'
    reseal(tampered)
    with pytest.raises(ValueError, match='only declare the observation level'):
        validate_cost_record(tampered)


def test_a_weakened_limitation_text_is_refused(record):
    tampered = deepcopy(record)
    tampered['limitation'] = 'cost is reproducible'
    reseal(tampered)
    with pytest.raises(ValueError, match='cost limitation text was altered'):
        validate_cost_record(tampered)


def test_stopwatch_measures_whole_nanoseconds():
    with Stopwatch() as watch:
        sum(range(1000))
    assert type(watch.wall_ns) is int
    assert watch.wall_ns >= 0


def test_runtime_context_is_json_serialisable_and_float_free():
    context = runtime_context()
    assert set(context) == {'python_version', 'platform', 'machine', 'max_recursion'}
    json.dumps(context)
    for value in context.values():
        assert type(value) in (str, int)

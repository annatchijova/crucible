from copy import deepcopy
import json

import pytest

from crucible.ir import digest_bytes, digest_payload
from crucible.replay import REPLAY_VERSION, dump_bundle, load_bundle, replay_readiness, validate_bundle


def seal(bundle):
    bundle['bundle_digest'] = digest_payload({k: v for k, v in bundle.items() if k != 'bundle_digest'})
    return bundle


@pytest.fixture
def bundle():
    task = {'task_id': 't1', 'task_prompt': 'Design retries.', 'properties': [
        {'property_id': 'p1', 'description': 'Bound retries.', 'check': 'mentions_budget'},
    ]}
    return seal({
        'schema_version': REPLAY_VERSION,
        'task': task, 'task_digest': digest_payload(task),
        'variants': [{'variant_id': 'original', 'skill_text': 'Use bounded retries.',
                      'skill_digest': digest_bytes(b'Use bounded retries.')}],
        'oracle': {'oracle_id': 'test-oracle/v1', 'implementation_digest': digest_bytes(b'fixture oracle')},
        'runs': [{
            'variant_id': 'original',
            'request': {'model': 'fixture', 'provider': 'local-fixture',
                        'system_prompt': 'Use bounded retries.', 'user_prompt': task['task_prompt'],
                        'temperature': 0, 'max_tokens': 100},
            'response': {'status': 'COMPLETED', 'output': 'Retry at most 3 times.',
                         'output_digest': digest_bytes(b'Retry at most 3 times.'),
                         'response_id': 'local-1', 'finish_reason': 'stop', 'truncated': False,
                         'usage': {'prompt_tokens': 5, 'completion_tokens': 6, 'total_tokens': 11},
                         'error': None},
            'observations': [{'property_id': 'p1', 'status': 'PASS', 'evidence': 'Three attempts.'}],
        }],
    })


def test_roundtrip_is_exact_and_does_not_mutate(bundle, monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *a, **k: pytest.fail('network called'))
    before = deepcopy(bundle)
    restored = load_bundle(dump_bundle(bundle))
    assert restored == before == bundle
    assert restored is not bundle
    assert replay_readiness(restored) == {'evidence_complete': True, 'incomplete_variants': []}


@pytest.mark.parametrize('mutation', ['task', 'skill', 'output', 'request', 'missing_run', 'oracle', 'duplicate_run'])
def test_resealed_internal_inconsistency_is_rejected(bundle, mutation):
    if mutation == 'task':
        bundle['task']['properties'][0]['description'] = 'Changed semantics'
    elif mutation == 'skill':
        bundle['variants'][0]['skill_text'] = 'Unbounded retries'
    elif mutation == 'output':
        bundle['runs'][0]['response']['output'] = 'altered'
    elif mutation == 'request':
        bundle['runs'][0]['request']['user_prompt'] = 'different task'
    elif mutation == 'missing_run':
        bundle['runs'] = []
    elif mutation == 'oracle':
        bundle['oracle']['implementation_digest'] = 'unknown'
    else:
        bundle['runs'].append(deepcopy(bundle['runs'][0]))
    with pytest.raises(ValueError):
        validate_bundle(seal(bundle))


def test_tamper_and_future_version_rejected(bundle):
    bundle['runs'][0]['observations'][0]['evidence'] = 'changed'
    with pytest.raises(ValueError, match='bundle digest'):
        validate_bundle(bundle)
    bundle['schema_version'] = 'crucible-replay-bundle/v99'
    with pytest.raises(ValueError, match='schema version'):
        validate_bundle(seal(bundle))


@pytest.mark.parametrize('key,value', [
    ('truncated', True), ('truncated', None), ('finish_reason', 'length'),
    ('status', 'ERROR'), ('status', 'BLOCKED'), ('error', 'provider failed'),
    ('usage', None), ('response_id', None),
])
def test_incomplete_evidence_is_preserved_not_replay_ready(bundle, key, value):
    bundle['runs'][0]['response'][key] = value
    seal(bundle)
    restored = load_bundle(dump_bundle(bundle))
    assert restored == bundle
    assert replay_readiness(restored)['evidence_complete'] is False


def test_missing_observations_are_not_complete(bundle):
    bundle['runs'][0]['observations'] = []
    assert not replay_readiness(seal(bundle))['evidence_complete']


def test_duplicate_json_keys_are_rejected(bundle):
    text = dump_bundle(bundle)
    text = '{"schema_version": "ignored",' + text[1:]
    with pytest.raises(ValueError, match='duplicate JSON'):
        load_bundle(text)


def test_credentials_and_legacy_shapes_are_not_accepted(bundle):
    bundle['runs'][0]['request']['api_key'] = 'dummy'
    with pytest.raises(ValueError, match='request'):
        validate_bundle(seal(bundle))
    with pytest.raises(ValueError, match='schema version'):
        load_bundle(json.dumps({'behavioral_version': 'crucible-behavioral/v1'}))


def test_size_limit_is_enforced_before_json_parse(bundle, monkeypatch):
    text = dump_bundle(bundle)
    monkeypatch.setattr('crucible.replay.MAX_BUNDLE_BYTES', 2)
    with pytest.raises(ValueError, match='byte limit'):
        load_bundle(text)

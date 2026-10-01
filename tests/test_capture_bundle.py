"""Capture-backed replay contracts, with a fake transport and no provider calls."""
import io
import json
from copy import deepcopy

import pytest

from crucible.behavioral import NebiusExecutor
from crucible.ir import digest_payload
from crucible.replay import dump_bundle, load_bundle, replay_readiness, validate_bundle


def reseal(value, key):
    value[key] = digest_payload({k: v for k, v in value.items() if k != key})


@pytest.fixture
def fake_provider(monkeypatch):
    payload = {'id': 'fake-response', 'choices': [{'message': {'content': 'Use at most 3 attempts.'},
                                               'finish_reason': 'stop'}],
               'usage': {'prompt_tokens': 3, 'completion_tokens': 6, 'total_tokens': 9}}
    requests = []

    class Response(io.BytesIO):
        def getcode(self):
            return 200

    def open_request(request, timeout):
        requests.append(request)
        return Response(json.dumps(payload).encode())

    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', open_request)
    return payload, requests


def capture_bundle():
    from crucible.capture_bundle import capture_behavioral_bundle
    return capture_behavioral_bundle(NebiusExecutor(api_key='dummy'))


def test_capture_bundle_preserves_baseline_and_roundtrips_offline(fake_provider, monkeypatch):
    bundle = capture_bundle()
    assert len(fake_provider[1]) == 4
    assert bundle['schema_version'] == 'crucible-replay-bundle/v2'
    baseline = bundle['runs'][0]['capture']
    assert bundle['variants'][0]['skill_text'] == ''
    assert baseline['guidance']['system_prompt'] == ''
    assert json.loads(baseline['request']['body'])['messages'][0]['content'] == 'You are a helpful assistant.'
    before = deepcopy(bundle)
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', lambda *a, **k: pytest.fail('network'))
    assert load_bundle(dump_bundle(bundle)) == before == bundle
    assert replay_readiness(bundle)['evidence_complete']


@pytest.mark.parametrize('mutation', ['guidance', 'wire', 'response_digest', 'status', 'attempted', 'extra', 'version'])
def test_resealed_capture_inconsistencies_fail(fake_provider, mutation):
    bundle = capture_bundle()
    capture = bundle['runs'][0]['capture']
    if mutation == 'guidance':
        capture['guidance']['user_prompt'] = 'another task'
    elif mutation == 'wire':
        request = json.loads(capture['request']['body'])
        request['messages'][0]['content'] = 'different guidance'
        capture['request']['body'] = json.dumps(request)
        from crucible.ir import digest_bytes
        capture['request']['body_digest'] = digest_bytes(capture['request']['body'].encode())
    elif mutation == 'response_digest':
        capture['response']['body_digest'] = 'sha256:' + '0' * 64
    elif mutation == 'status':
        capture['status'] = 'BLOCKED'
    elif mutation == 'attempted':
        capture['attempted'] = False
    elif mutation == 'extra':
        capture['request']['Authorization'] = 'dummy'
    else:
        capture['schema_version'] = 'future/v99'
    reseal(capture, 'capture_digest')
    reseal(bundle, 'bundle_digest')
    with pytest.raises(ValueError):
        validate_bundle(bundle)


@pytest.mark.parametrize('field', ['usage', 'id', 'finish_reason', 'truncation'])
def test_missing_or_truncated_metadata_never_becomes_ready(fake_provider, field):
    payload, _ = fake_provider
    if field in ('usage', 'id'):
        payload.pop(field)
    elif field == 'finish_reason':
        payload['choices'][0].pop('finish_reason')
    else:
        payload['choices'][0]['finish_reason'] = 'length'
    bundle = capture_bundle()
    assert load_bundle(dump_bundle(bundle)) == bundle
    assert not replay_readiness(bundle)['evidence_complete']


def test_blocked_bundle_has_no_fallback_or_network(monkeypatch):
    from crucible.capture_bundle import capture_behavioral_bundle
    monkeypatch.delenv('NEBIUS_API_KEY', raising=False)
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', lambda *a, **k: pytest.fail('network'))
    bundle = capture_behavioral_bundle(NebiusExecutor())
    assert len(bundle['runs']) == 4
    assert all(run['capture']['status'] == 'BLOCKED' and not run['observations'] for run in bundle['runs'])
    assert not replay_readiness(bundle)['evidence_complete']


def test_oracle_identity_is_pinned_not_supplied_by_provider(fake_provider):
    from crucible.capture_bundle import oracle_identity
    fake_provider[0]['oracle'] = {'oracle_id': 'attacker'}
    assert capture_bundle()['oracle'] == oracle_identity()


@pytest.mark.parametrize('raw', [b'not JSON', b'\xff', b'{"choices":[],"choices":[]}',
                               b'{"choices":[],"value":NaN}'])
def test_malformed_response_is_retained_but_not_observed(monkeypatch, raw):
    import base64
    class Response(io.BytesIO):
        def getcode(self):
            return 200
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', lambda *a, **k: Response(raw))
    bundle = capture_bundle()
    assert all(not run['observations'] for run in bundle['runs'])
    assert base64.b64decode(bundle['runs'][0]['capture']['response']['body_base64']) == raw
    assert not replay_readiness(load_bundle(dump_bundle(bundle)))['evidence_complete']


@pytest.mark.parametrize('mutation', ['bool_usage', 'missing_usage_field', 'inconsistent_usage', 'null_content'])
def test_provider_metadata_does_not_get_coerced_to_success(fake_provider, mutation):
    payload, _ = fake_provider
    if mutation == 'bool_usage':
        payload['usage']['prompt_tokens'] = True
    elif mutation == 'missing_usage_field':
        payload['usage'].pop('total_tokens')
    elif mutation == 'inconsistent_usage':
        payload['usage']['total_tokens'] = 100
    else:
        payload['choices'][0]['message']['content'] = None
    assert not replay_readiness(capture_bundle())['evidence_complete']


@pytest.mark.parametrize('mutation', ['adapter', 'task', 'variant', 'outer_seal', 'capture_seal', 'base64'])
def test_cross_links_and_seals_are_required(fake_provider, mutation):
    bundle = capture_bundle()
    if mutation == 'adapter':
        bundle['request_adapter'] = 'future/v2'
    elif mutation == 'task':
        bundle['task']['task_prompt'] = 'other task'
        bundle['task_digest'] = digest_payload(bundle['task'])
    elif mutation == 'variant':
        bundle['runs'][0]['variant_id'] = bundle['runs'][1]['variant_id']
    elif mutation == 'outer_seal':
        bundle['bundle_digest'] = 'sha256:' + '0' * 64
    elif mutation == 'capture_seal':
        bundle['runs'][0]['capture']['capture_digest'] = 'sha256:' + '0' * 64
    else:
        bundle['runs'][0]['capture']['response']['body_base64'] = 'not base64!'
        reseal(bundle['runs'][0]['capture'], 'capture_digest')
    if mutation != 'outer_seal':
        reseal(bundle, 'bundle_digest')
    with pytest.raises(ValueError):
        load_bundle(json.dumps(bundle))


def test_capture_limit_stops_before_next_call_and_retains_partial_evidence(fake_provider, monkeypatch):
    from crucible.capture_bundle import CaptureAssemblyError
    # Inputs fit; the first captured response exceeds the aggregate allowance.
    monkeypatch.setattr('crucible.replay.MAX_BUNDLE_BYTES', 7000)
    fake_provider[0]['choices'][0]['message']['content'] = 'x' * 5000
    with pytest.raises(CaptureAssemblyError) as exc:
        capture_bundle()
    assert len(fake_provider[1]) == 1
    partial = exc.value.partial_evidence
    assert len(partial['runs']) == 1
    assert 'schema_version' not in partial and 'bundle_digest' not in partial


def test_invalid_experiment_fails_before_network(monkeypatch):
    from crucible.capture_bundle import capture_behavioral_bundle
    from crucible.behavioral import TASK_FIXTURE, ALL_VARIANTS
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', lambda *a, **k: pytest.fail('network'))
    task = deepcopy(TASK_FIXTURE)
    task['properties'].append(deepcopy(task['properties'][0]))
    with pytest.raises(ValueError, match='duplicate property'):
        capture_behavioral_bundle(NebiusExecutor(api_key='dummy'), task=task)
    with pytest.raises(ValueError, match='duplicate variant'):
        capture_behavioral_bundle(NebiusExecutor(api_key='dummy'), variants=[ALL_VARIANTS[0]] * 2)


def test_loader_never_executes_oracle(fake_provider, monkeypatch):
    bundle = capture_bundle()
    monkeypatch.setattr('crucible.behavioral.run_property_oracle', lambda *a, **k: pytest.fail('oracle'))
    assert load_bundle(dump_bundle(bundle)) == bundle


def test_oracle_drift_retains_evidence_but_does_not_return_bundle(fake_provider, monkeypatch):
    from crucible.capture_bundle import CaptureAssemblyError, oracle_identity
    initial = oracle_identity()
    identities = iter([initial, {**initial, 'implementation_digest': 'sha256:' + '0' * 64}])
    monkeypatch.setattr('crucible.capture_bundle.oracle_identity', lambda: next(identities))
    with pytest.raises(CaptureAssemblyError, match='oracle changed') as exc:
        capture_bundle()
    assert len(exc.value.partial_evidence['runs']) == 4


def test_inputs_are_frozen_before_first_capture(fake_provider):
    from crucible.capture_bundle import capture_behavioral_bundle
    from crucible.behavioral import TASK_FIXTURE, ALL_VARIANTS
    task, variants = deepcopy(TASK_FIXTURE), deepcopy(ALL_VARIANTS)
    expected = deepcopy(task)
    class MutatingCaller:
        def capture_exchange(self, system_prompt, user_prompt):
            task['task_prompt'] = 'changed outside'
            variants[1]['skill_text'] = 'changed outside'
            return NebiusExecutor(api_key='dummy').capture_exchange(system_prompt, user_prompt)
    bundle = capture_behavioral_bundle(MutatingCaller(), task, variants)
    assert bundle['task']['task_prompt'] == expected['task_prompt']
    assert bundle['variants'][1]['skill_text'] == ALL_VARIANTS[1]['skill_text']


def test_error_response_cannot_carry_fabricated_observations(fake_provider):
    fake_provider[0]['choices'][0]['message']['content'] = None
    bundle = capture_bundle()
    bundle['runs'][0]['observations'] = [{'property_id': bundle['task']['properties'][0]['property_id'],
                                         'status': 'PASS', 'evidence': 'invented'}]
    reseal(bundle, 'bundle_digest')
    with pytest.raises(ValueError, match='observations require'):
        validate_bundle(bundle)

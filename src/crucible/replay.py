"""Offline storage contract for replay evidence; never executes an oracle/provider.

A valid digest proves byte integrity, not provider provenance or acceptance.
Historical behavioral/v1 artifacts are not silently upgraded to this format.
"""

from copy import deepcopy
import json
import re

from .ir import canonical_bytes, digest_bytes, digest_payload

REPLAY_VERSION = 'crucible-replay-bundle/v1'
CAPTURE_REPLAY_VERSION = 'crucible-replay-bundle/v2'
MAX_BUNDLE_BYTES = 8_000_000
_DIGEST = re.compile(r'sha256:[0-9a-f]{64}\Z')


def _fields(value, names, label):
    if type(value) is not dict or set(value) != set(names.split()):
        raise ValueError(f'{label}: invalid fields')


def _text(value, label, *, empty=False):
    if type(value) is not str or (not empty and not value):
        raise ValueError(f'{label}: expected text')


def _digest(value, label):
    if type(value) is not str or not _DIGEST.fullmatch(value):
        raise ValueError(f'{label}: invalid digest')


def validate_bundle(bundle):
    """Check schema, seals and cross-links, returning an independent copy."""
    if type(bundle) is not dict or bundle.get('schema_version') not in (REPLAY_VERSION, CAPTURE_REPLAY_VERSION):
        raise ValueError('unsupported replay schema version')
    captured = bundle['schema_version'] == CAPTURE_REPLAY_VERSION
    fields = 'schema_version task task_digest variants oracle runs bundle_digest'
    _fields(bundle, fields + (' request_adapter' if captured else ''), 'bundle')
    if captured:
        from .capture_contract import ADAPTER_VERSION, capture_projection
        if bundle['request_adapter'] != ADAPTER_VERSION:
            raise ValueError('unsupported request adapter')
    if len(canonical_bytes(bundle)) > MAX_BUNDLE_BYTES:
        raise ValueError('replay bundle exceeds byte limit')
    task = bundle['task']
    _fields(task, 'task_id task_prompt properties', 'task')
    _text(task['task_id'], 'task_id')
    _text(task['task_prompt'], 'task_prompt')
    if type(task['properties']) is not list or not 1 <= len(task['properties']) <= 100:
        raise ValueError('invalid properties')
    property_ids = set()
    for prop in task['properties']:
        _fields(prop, 'property_id description check', 'property')
        for key in prop:
            _text(prop[key], key)
        if prop['property_id'] in property_ids:
            raise ValueError('duplicate property')
        property_ids.add(prop['property_id'])
    if bundle['task_digest'] != digest_payload(task):
        raise ValueError('task digest mismatch')
    _fields(bundle['oracle'], 'oracle_id implementation_digest', 'oracle')
    _text(bundle['oracle']['oracle_id'], 'oracle_id')
    _digest(bundle['oracle']['implementation_digest'], 'oracle implementation')
    variants = bundle['variants']
    if type(variants) is not list or not 1 <= len(variants) <= 500:
        raise ValueError('invalid variants')
    by_id = {}
    for variant in variants:
        _fields(variant, 'variant_id skill_text skill_digest', 'variant')
        _text(variant['variant_id'], 'variant_id')
        _text(variant['skill_text'], 'skill_text', empty=True)
        if variant['variant_id'] in by_id:
            raise ValueError('duplicate variant')
        if variant['skill_digest'] != digest_bytes(variant['skill_text'].encode('utf-8')):
            raise ValueError('skill digest mismatch')
        by_id[variant['variant_id']] = variant
    if type(bundle['runs']) is not list or len(bundle['runs']) != len(variants):
        raise ValueError('one run per variant is required')
    seen = set()
    for run in bundle['runs']:
        _fields(run, 'variant_id capture observations' if captured else 'variant_id request response observations', 'run')
        _text(run['variant_id'], 'run variant_id')
        variant_id = run['variant_id']
        if variant_id not in by_id or variant_id in seen:
            raise ValueError('unknown or duplicate run variant')
        seen.add(variant_id)
        if captured:
            request, response = capture_projection(run['capture'])
            if run['capture']['guidance'] != {'system_prompt': by_id[variant_id]['skill_text'],
                                              'user_prompt': task['task_prompt']}:
                raise ValueError('capture task/variant mismatch')
        else:
            request, response = run['request'], run['response']
        _fields(request, 'model provider system_prompt user_prompt temperature max_tokens', 'request')
        for key in ('model', 'provider', 'user_prompt'):
            _text(request[key], key)
        _text(request['system_prompt'], 'system_prompt', empty=True)
        for key in ('temperature', 'max_tokens'):
            if type(request[key]) is not int or request[key] < 0:
                raise ValueError(f'{key}: expected nonnegative integer')
        if request['user_prompt'] != task['task_prompt']:
            raise ValueError('request task mismatch')
        if not captured and request['system_prompt'] != by_id[variant_id]['skill_text']:
            raise ValueError('request variant mismatch')
        _fields(response, 'status output output_digest response_id finish_reason truncated usage error', 'response')
        if response['status'] not in ('COMPLETED', 'ERROR', 'BLOCKED'):
            raise ValueError('invalid response status')
        _text(response['output'], 'output', empty=True)
        if response['output_digest'] != digest_bytes(response['output'].encode('utf-8')):
            raise ValueError('output digest mismatch')
        for key in ('response_id', 'finish_reason', 'error'):
            if response[key] is not None:
                _text(response[key], key)
        if response['truncated'] is not None and type(response['truncated']) is not bool:
            raise ValueError('invalid truncated metadata')
        if response['usage'] is not None:
            _fields(response['usage'], 'prompt_tokens completion_tokens total_tokens', 'usage')
            if any(type(v) is not int or v < 0 for v in response['usage'].values()):
                raise ValueError('invalid usage counts')
        observations = run['observations']
        if type(observations) is not list or len(observations) > len(property_ids):
            raise ValueError('invalid observations')
        if captured and response['status'] != 'COMPLETED' and observations:
            raise ValueError('observations require captured textual output')
        observed = set()
        for observation in observations:
            _fields(observation, 'property_id status evidence', 'observation')
            _text(observation['property_id'], 'observation property_id')
            pid = observation['property_id']
            if pid not in property_ids or pid in observed:
                raise ValueError('unknown or duplicate observation')
            if observation['status'] not in ('PASS', 'FAIL', 'ABSTAINED'):
                raise ValueError('invalid observation status')
            _text(observation['evidence'], 'observation evidence')
            observed.add(pid)
    payload = {k: v for k, v in bundle.items() if k != 'bundle_digest'}
    if bundle['bundle_digest'] != digest_payload(payload):
        raise ValueError('bundle digest mismatch')
    return deepcopy(bundle)


def replay_readiness(bundle):
    """Report incomplete evidence; readiness is NOT a repair acceptance verdict."""
    bundle = validate_bundle(bundle)
    reasons = []
    for run in bundle['runs']:
        if bundle['schema_version'] == CAPTURE_REPLAY_VERSION:
            from .capture_contract import capture_projection
            _, response = capture_projection(run['capture'])
        else:
            response = run['response']
        if (response['status'] != 'COMPLETED' or response['error'] is not None
                or response['truncated'] is not False or not response['output']
                or response['finish_reason'] != 'stop' or not response['response_id']
                or response['usage'] is None
                or len(run['observations']) != len(bundle['task']['properties'])):
            reasons.append(run['variant_id'])
    return {'evidence_complete': not reasons, 'incomplete_variants': reasons}


def dump_bundle(bundle):
    return canonical_bytes(validate_bundle(bundle)).decode('utf-8')


def load_bundle(text):
    if type(text) is not str or len(text.encode('utf-8')) > MAX_BUNDLE_BYTES:
        raise ValueError('invalid replay JSON or byte limit exceeded')

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError('nonfinite JSON')

    try:
        value = json.loads(text, object_pairs_hook=unique_pairs,
                           parse_constant=reject_constant)
        return validate_bundle(value)
    except (RecursionError, TypeError, KeyError) as exc:
        raise ValueError('invalid replay structure') from exc

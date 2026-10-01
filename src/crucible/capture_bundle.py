"""Acquire a new capture-backed experiment; never reconstruct historical runs."""

from copy import deepcopy
import inspect
import sys

from . import behavioral
from . import replay
from .capture_contract import ADAPTER_VERSION, capture_projection
from .ir import canonical_bytes, digest_bytes, digest_payload
from .replay import CAPTURE_REPLAY_VERSION, _fields, _text, validate_bundle


class CaptureAssemblyError(ValueError):
    """Assembly stopped; private evidence remains available, but is not a bundle."""

    def __init__(self, reason, bundle):
        super().__init__(reason)
        self.partial_evidence = {key: value for key, value in bundle.items()
                                 if key not in ('schema_version', 'bundle_digest')}


def oracle_identity():
    """Pin the lexical oracle sources, helper sources, dispatch and Python runtime.

    Local code/source files are trusted. This is not loaded-code attestation.
    R3 must compare this identity before executing the local oracle.
    """
    functions = [behavioral.run_property_oracle, behavioral._has_negation,
                 behavioral._normalize_oracle_text]
    functions += [fn for _, fn in sorted(behavioral.PROPERTY_CHECKS.items())]
    manifest = {
        'python': sys.version,
        'dispatch': {key: fn.__name__ for key, fn in sorted(behavioral.PROPERTY_CHECKS.items())},
        'sources': [inspect.getsource(fn) for fn in functions],
    }
    return {'oracle_id': 'crucible-lexical-properties/v1',
            'implementation_digest': digest_payload(manifest)}


def capture_behavioral_bundle(executor, task=None, variants=None, *, journal=None):
    """Capture a fresh experiment with frozen inputs and no implicit fallback.

    This function can call the provider. Storage validation/loading never does.
    Each retained capture is bound to exact task/variant text and historical
    observations from the pinned local oracle. No accept/reject decision is made.
    """
    task = deepcopy(behavioral.TASK_FIXTURE if task is None else task)
    variants = deepcopy(behavioral.ALL_VARIANTS if variants is None else variants)
    if type(task) is not dict:
        raise ValueError('invalid task')
    # Legacy fixture digests omit properties; compute the new contract's full seal.
    task.pop('task_digest', None)
    _fields(task, 'task_id task_prompt properties', 'task')
    for key in ('task_id', 'task_prompt'):
        _text(task[key], key)
    if type(task['properties']) is not list or not 1 <= len(task['properties']) <= 100:
        raise ValueError('invalid properties')
    ids = set()
    for prop in task['properties']:
        _fields(prop, 'property_id description check', 'property')
        for key in prop:
            _text(prop[key], key)
        if prop['property_id'] in ids:
            raise ValueError('duplicate property')
        ids.add(prop['property_id'])
    if type(variants) is not list or not 1 <= len(variants) <= 500:
        raise ValueError('invalid variants')
    prepared, ids = [], set()
    for variant in variants:
        if type(variant) is not dict or set(variant) - {'variant_id', 'description', 'skill_text'}:
            raise ValueError('invalid variant fields')
        _text(variant.get('variant_id'), 'variant_id')
        _text(variant.get('skill_text'), 'skill_text', empty=True)
        if variant['variant_id'] in ids:
            raise ValueError('duplicate variant')
        ids.add(variant['variant_id'])
        prepared.append({'variant_id': variant['variant_id'], 'skill_text': variant['skill_text'],
                         'skill_digest': digest_bytes(variant['skill_text'].encode('utf-8'))})
    oracle = oracle_identity()
    bundle = {'schema_version': CAPTURE_REPLAY_VERSION, 'request_adapter': ADAPTER_VERSION,
              'task': task, 'task_digest': digest_payload(task), 'variants': prepared,
              'oracle': oracle, 'runs': []}
    if len(canonical_bytes(bundle)) + 100 > replay.MAX_BUNDLE_BYTES:
        raise ValueError('experiment inputs exceed bundle byte limit')
    if journal is not None:
        journal.start(deepcopy(bundle))
    for variant in prepared:
        capture = executor.capture_exchange(variant['skill_text'], task['task_prompt'])
        if journal is not None:
            journal.record_capture(variant['variant_id'], deepcopy(capture))
        _, response = capture_projection(capture)
        if capture['guidance'] != {'system_prompt': variant['skill_text'], 'user_prompt': task['task_prompt']}:
            raise ValueError('capture task/variant mismatch')
        observations = []
        if response['status'] == 'COMPLETED':
            observations = [{key: obs[key] for key in ('property_id', 'status', 'evidence')}
                            for obs in behavioral.run_property_oracle(response['output'], task['properties'])]
        bundle['runs'].append({'variant_id': variant['variant_id'], 'capture': capture,
                               'observations': observations})
        if journal is not None:
            journal.record_observations(variant['variant_id'], deepcopy(observations))
        # Bound accumulation before another provider call; preserve the last capture
        # in the exception rather than discard it or pretend a partial bundle passed.
        if len(canonical_bytes(bundle)) + 100 > replay.MAX_BUNDLE_BYTES:
            raise CaptureAssemblyError('captured experiment exceeds bundle byte limit', bundle)
    if oracle_identity() != oracle:
        raise CaptureAssemblyError('oracle changed during capture', bundle)
    bundle['bundle_digest'] = digest_payload(bundle)
    bundle = validate_bundle(bundle)
    if journal is not None:
        journal.finish(bundle)
    return bundle

"""Frozen identity and evaluation role for an external skill corpus.

A corpus claim is only reproducible if the exact analyzed bytes can be named
again later. This module derives that identity from a compiled Skill IR, so the
manifest describes what the auditor actually read rather than a parallel
filesystem walk that could diverge from it.

Two separate things are recorded, and they carry different authority:

* ``manifest_digest`` is verifiable. It seals the sorted per-skill name, source
  path and content digest, so recompiling the corpus either reproduces it or
  does not.
* ``source_reference`` (repository and commit) is a recorded claim. The seal
  binds the claim to the bytes, but nothing here proves the bytes came from
  that commit. :func:`verify_against_ir` checks byte identity only.

``role`` makes the tuning/held-out separation enforceable instead of merely
documented. A corpus used to fix the analyzer cannot support a generalization
claim, so ``HELDOUT_SEALED`` rejects any recorded consumption.
"""

from collections import Counter
from copy import deepcopy

from .ir import SCHEMA_VERSION, digest_payload
from .replay import _digest, _fields, _text

CORPUS_PROVENANCE_VERSION = 'corpus-provenance/v1'

ROLE_REGRESSION = 'REGRESSION'
ROLE_TUNING_CONSUMED = 'TUNING_CONSUMED'
ROLE_HELDOUT_SEALED = 'HELDOUT_SEALED'
ROLES = (ROLE_REGRESSION, ROLE_TUNING_CONSUMED, ROLE_HELDOUT_SEALED)

_MAX_SKILLS = 100_000
_MAX_CONSUMED_BY = 1_000


def build_provenance(ir, *, corpus_id, role, repository, commit,
                     consumed_by=()):
    """Seal the corpus identity carried by a compiled Skill IR artifact."""
    if type(ir) is not dict or ir.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('unsupported corpus IR schema version')
    _text(corpus_id, 'corpus_id')
    _text(repository, 'repository')
    _text(commit, 'commit')
    if role not in ROLES:
        raise ValueError('invalid corpus role')
    skills = ir.get('skills')
    if type(skills) is not list or not skills:
        raise ValueError('corpus IR carries no skills')
    if len(skills) > _MAX_SKILLS:
        raise ValueError('corpus skill limit exceeded')
    references = [str(item) for item in consumed_by]
    if len(references) > _MAX_CONSUMED_BY:
        raise ValueError('consumed_by limit exceeded')
    manifest = _manifest(skills)
    payload = {
        'schema_version': CORPUS_PROVENANCE_VERSION,
        'corpus_id': corpus_id,
        'role': role,
        'consumed_by': sorted(references),
        'source_reference': {'repository': repository, 'commit': commit},
        'skill_count': len(manifest),
        'skills': manifest,
        'manifest_digest': digest_payload(manifest),
        'input_artifact_digest': ir['artifact_digest'],
        'input_schema_version': ir['schema_version'],
    }
    _check_role_consistency(payload)
    payload['provenance_digest'] = digest_payload(payload)
    return payload


def validate_provenance(record):
    """Check schema, seals and role consistency, returning an independent copy."""
    if type(record) is not dict or record.get('schema_version') != CORPUS_PROVENANCE_VERSION:
        raise ValueError('unsupported corpus provenance schema version')
    _fields(
        record,
        'schema_version corpus_id role consumed_by source_reference skill_count '
        'skills manifest_digest input_artifact_digest input_schema_version '
        'provenance_digest',
        'corpus provenance',
    )
    _text(record['corpus_id'], 'corpus_id')
    if record['role'] not in ROLES:
        raise ValueError('invalid corpus role')
    if type(record['consumed_by']) is not list:
        raise ValueError('consumed_by: expected list')
    for reference in record['consumed_by']:
        _text(reference, 'consumed_by entry')
    if record['consumed_by'] != sorted(record['consumed_by']):
        raise ValueError('consumed_by is not canonically ordered')
    _fields(record['source_reference'], 'repository commit', 'source_reference')
    _text(record['source_reference']['repository'], 'repository')
    _text(record['source_reference']['commit'], 'commit')
    _digest(record['input_artifact_digest'], 'input_artifact_digest')
    if record['input_schema_version'] != SCHEMA_VERSION:
        raise ValueError('unsupported corpus IR schema version')
    skills = record['skills']
    if type(skills) is not list or not skills:
        raise ValueError('corpus provenance carries no skills')
    if len(skills) > _MAX_SKILLS:
        raise ValueError('corpus skill limit exceeded')
    if type(record['skill_count']) is not int or record['skill_count'] != len(skills):
        raise ValueError('skill_count does not match the manifest')
    for entry in skills:
        _fields(entry, 'name source_path content_digest', 'manifest entry')
        _text(entry['name'], 'manifest name')
        _text(entry['source_path'], 'manifest source_path')
        _digest(entry['content_digest'], 'manifest content_digest')
    if skills != _sorted_manifest(skills):
        raise ValueError('manifest is not canonically ordered')
    if record['manifest_digest'] != digest_payload(skills):
        raise ValueError('manifest digest mismatch')
    _check_role_consistency(record)
    sealed = {key: value for key, value in record.items() if key != 'provenance_digest'}
    if record['provenance_digest'] != digest_payload(sealed):
        raise ValueError('provenance digest mismatch')
    return deepcopy(record)


def verify_against_ir(record, ir):
    """Report whether a freshly compiled IR reproduces the sealed manifest.

    Byte identity only. Agreement does not establish that the bytes came from
    the recorded repository or commit.
    """
    validated = validate_provenance(record)
    if type(ir) is not dict or ir.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('unsupported corpus IR schema version')
    skills = ir.get('skills')
    if type(skills) is not list or not skills:
        raise ValueError('corpus IR carries no skills')
    observed = _manifest(skills)
    sealed_paths = {entry['source_path']: entry for entry in validated['skills']}
    observed_paths = {entry['source_path']: entry for entry in observed}
    changed = sorted(
        path for path in sealed_paths.keys() & observed_paths.keys()
        if sealed_paths[path] != observed_paths[path]
    )
    return {
        'schema_version': CORPUS_PROVENANCE_VERSION,
        'corpus_id': validated['corpus_id'],
        'manifest_digest': validated['manifest_digest'],
        'observed_manifest_digest': digest_payload(observed),
        'observed_artifact_digest': ir['artifact_digest'],
        'outcome': 'MATCH' if observed == validated['skills'] else 'MISMATCH',
        'missing': sorted(sealed_paths.keys() - observed_paths.keys()),
        'unexpected': sorted(observed_paths.keys() - sealed_paths.keys()),
        'changed': changed,
        'limitation': 'byte identity only; the recorded repository and commit are '
                      'not verified by this check',
    }


def _manifest(skills):
    entries = []
    for skill in skills:
        if type(skill) is not dict:
            raise ValueError('corpus IR skill: expected object')
        identity = skill.get('identity')
        _fields(identity, 'name source_path content_digest', 'corpus IR identity')
        _text(identity['name'], 'corpus IR name')
        _text(identity['source_path'], 'corpus IR source_path')
        _digest(identity['content_digest'], 'corpus IR content_digest')
        entries.append(dict(identity))
    counts = Counter(entry['source_path'] for entry in entries)
    duplicates = sorted(path for path, total in counts.items() if total > 1)
    if duplicates:
        raise ValueError(f"duplicate corpus source path(s): {', '.join(duplicates)}")
    return _sorted_manifest(entries)


def _sorted_manifest(entries):
    return sorted(entries, key=lambda entry: (entry['source_path'], entry['name']))


def _check_role_consistency(record):
    if record['role'] == ROLE_HELDOUT_SEALED and record['consumed_by']:
        raise ValueError('a HELDOUT_SEALED corpus cannot record consumption')
    if record['role'] == ROLE_TUNING_CONSUMED and not record['consumed_by']:
        raise ValueError('a TUNING_CONSUMED corpus must record what consumed it')

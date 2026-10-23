"""Frozen corpus identity, role separation and reproduction contracts."""
import json
from copy import deepcopy

import pytest

from crucible.compiler import compile_corpus
from crucible.corpus_provenance import (
    CORPUS_PROVENANCE_VERSION,
    ROLE_HELDOUT_SEALED,
    ROLE_REGRESSION,
    ROLE_TUNING_CONSUMED,
    build_provenance,
    validate_provenance,
    verify_against_ir,
)
from crucible.ir import digest_payload

CORPUS = 'tests/fixtures/diverse-corpus'


def reseal(record):
    record['provenance_digest'] = digest_payload(
        {k: v for k, v in record.items() if k != 'provenance_digest'}
    )


@pytest.fixture
def ir():
    return compile_corpus(CORPUS)


@pytest.fixture
def record(ir):
    return build_provenance(
        ir, corpus_id='diverse-corpus', role=ROLE_REGRESSION,
        repository='https://example.invalid/corpus.git', commit='0' * 40,
    )


def test_provenance_seals_the_analyzed_manifest(record, ir):
    assert record['schema_version'] == CORPUS_PROVENANCE_VERSION
    assert record['skill_count'] == len(ir['skills']) == len(record['skills'])
    assert record['input_artifact_digest'] == ir['artifact_digest']
    assert record['manifest_digest'] == digest_payload(record['skills'])
    assert validate_provenance(record) == record


def test_manifest_entries_mirror_compiled_identities(record, ir):
    sealed = {entry['source_path']: entry for entry in record['skills']}
    for skill in ir['skills']:
        identity = skill['identity']
        assert sealed[identity['source_path']] == identity


def test_identity_is_reproducible_across_recompilation(record):
    second = build_provenance(
        compile_corpus(CORPUS), corpus_id='diverse-corpus', role=ROLE_REGRESSION,
        repository='https://example.invalid/corpus.git', commit='0' * 40,
    )
    assert second == record


def test_manifest_order_is_canonical_not_discovery_order(record):
    paths = [entry['source_path'] for entry in record['skills']]
    assert paths == sorted(paths)


def test_validation_rejects_a_tampered_content_digest(record):
    tampered = deepcopy(record)
    tampered['skills'][0]['content_digest'] = f"sha256:{'a' * 64}"
    with pytest.raises(ValueError, match='manifest digest mismatch'):
        validate_provenance(tampered)


def test_a_fully_resealed_substitution_is_undetectable_offline(record):
    """A seal proves internal consistency, not that the bytes are the real ones.

    Anyone who can edit the record can also recompute every digest in it.
    Detecting that requires recompiling the corpus, so the honest boundary is
    that ``validate_provenance`` accepts this record and ``verify_against_ir``
    rejects it.
    """
    tampered = deepcopy(record)
    tampered['skills'][0]['content_digest'] = f"sha256:{'a' * 64}"
    tampered['manifest_digest'] = digest_payload(tampered['skills'])
    reseal(tampered)
    assert validate_provenance(tampered) == tampered
    result = verify_against_ir(tampered, compile_corpus(CORPUS))
    assert result['outcome'] == 'MISMATCH'
    assert result['changed'] == [tampered['skills'][0]['source_path']]


def test_validation_rejects_a_dropped_skill(record):
    tampered = deepcopy(record)
    del tampered['skills'][0]
    tampered['manifest_digest'] = digest_payload(tampered['skills'])
    reseal(tampered)
    with pytest.raises(ValueError, match='skill_count does not match'):
        validate_provenance(tampered)


def test_validation_rejects_a_rewritten_source_reference(record):
    tampered = deepcopy(record)
    tampered['source_reference']['commit'] = '1' * 40
    with pytest.raises(ValueError, match='provenance digest mismatch'):
        validate_provenance(tampered)


def test_heldout_corpus_cannot_record_consumption(ir):
    with pytest.raises(ValueError, match='HELDOUT_SEALED corpus cannot record consumption'):
        build_provenance(
            ir, corpus_id='heldout', role=ROLE_HELDOUT_SEALED,
            repository='https://example.invalid/corpus.git', commit='0' * 40,
            consumed_by=('docs/evidence/some-fix.md',),
        )


def test_a_sealed_heldout_record_cannot_be_edited_into_a_consumed_one(ir):
    sealed = build_provenance(
        ir, corpus_id='heldout', role=ROLE_HELDOUT_SEALED,
        repository='https://example.invalid/corpus.git', commit='0' * 40,
    )
    tampered = deepcopy(sealed)
    tampered['consumed_by'] = ['docs/evidence/some-fix.md']
    reseal(tampered)
    with pytest.raises(ValueError, match='HELDOUT_SEALED corpus cannot record consumption'):
        validate_provenance(tampered)


def test_tuning_corpus_must_name_what_consumed_it(ir):
    with pytest.raises(ValueError, match='must record what consumed it'):
        build_provenance(
            ir, corpus_id='tuning', role=ROLE_TUNING_CONSUMED,
            repository='https://example.invalid/corpus.git', commit='0' * 40,
        )
    consumed = build_provenance(
        ir, corpus_id='tuning', role=ROLE_TUNING_CONSUMED,
        repository='https://example.invalid/corpus.git', commit='0' * 40,
        consumed_by=('docs/evidence/b.md', 'docs/evidence/a.md'),
    )
    assert consumed['consumed_by'] == ['docs/evidence/a.md', 'docs/evidence/b.md']
    assert validate_provenance(consumed) == consumed


def test_unknown_role_is_rejected(ir):
    with pytest.raises(ValueError, match='invalid corpus role'):
        build_provenance(
            ir, corpus_id='corpus', role='HELDOUT',
            repository='https://example.invalid/corpus.git', commit='0' * 40,
        )


def test_verification_matches_an_unchanged_corpus(record):
    result = verify_against_ir(record, compile_corpus(CORPUS))
    assert result['outcome'] == 'MATCH'
    assert result['missing'] == result['unexpected'] == result['changed'] == []
    assert result['observed_manifest_digest'] == record['manifest_digest']
    assert 'not verified' in result['limitation']


def test_verification_reports_changed_missing_and_unexpected_paths(record, ir):
    drifted = deepcopy(ir)
    drifted['skills'][0]['identity']['content_digest'] = f"sha256:{'b' * 64}"
    moved = deepcopy(drifted['skills'][1])
    moved['identity']['source_path'] = 'relocated/SKILL.md'
    drifted['skills'][1] = moved
    changed_path = record['skills'][0]['source_path']
    result = verify_against_ir(record, drifted)
    assert result['outcome'] == 'MISMATCH'
    assert result['unexpected'] == ['relocated/SKILL.md']
    assert len(result['missing']) == 1
    assert changed_path in result['changed'] or changed_path in result['missing']


def test_verification_does_not_mutate_its_inputs(record, ir):
    before_record, before_ir = json.dumps(record, sort_keys=True), json.dumps(ir, sort_keys=True)
    verify_against_ir(record, ir)
    assert json.dumps(record, sort_keys=True) == before_record
    assert json.dumps(ir, sort_keys=True) == before_ir


def test_mismatched_ir_schema_is_refused(record, ir):
    stale = deepcopy(ir)
    stale['schema_version'] = 'skill-ir/v0'
    with pytest.raises(ValueError, match='unsupported corpus IR schema version'):
        verify_against_ir(record, stale)


def test_duplicate_source_paths_are_rejected(ir):
    from copy import deepcopy as _copy
    clashing = _copy(ir)
    clone = _copy(clashing['skills'][0])
    clone['identity']['name'] = 'renamed-clone'
    clashing['skills'].append(clone)
    with pytest.raises(ValueError, match='duplicate corpus source path'):
        build_provenance(
            clashing, corpus_id='clashing', role=ROLE_REGRESSION,
            repository='https://example.invalid/corpus.git', commit='0' * 40,
        )


def test_duplicate_detection_does_not_rescan_the_manifest_per_entry():
    """A quadratic duplicate scan would hang long before this returns.

    The manifest bound is 100k skills, where names.count(name)-style detection
    costs ~5e9 comparisons. Counting once keeps it linear, so this stays fast.
    """
    from crucible.ir import SCHEMA_VERSION as _SV
    skills = [
        {'identity': {'name': f'skill-{index:06d}',
                      'source_path': f'skill-{index:06d}/SKILL.md',
                      'content_digest': f"sha256:{index:064x}"}}
        for index in range(20_000)
    ]
    artifact = {'schema_version': _SV, 'skills': skills, 'artifact_digest': f"sha256:{'c' * 64}"}
    record = build_provenance(
        artifact, corpus_id='large', role=ROLE_REGRESSION,
        repository='https://example.invalid/corpus.git', commit='0' * 40,
    )
    assert record['skill_count'] == 20_000

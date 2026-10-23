"""A corpus with colliding skill names is refused or analyzed with honest coverage."""
import pytest

from crucible.auditor import audit_corpus
from crucible.cli import main
from crucible.compiler import (
    EXCLUDED_DISTINCT,
    EXCLUDED_IDENTICAL,
    ON_DUPLICATE_ERROR,
    ON_DUPLICATE_SKIP,
    compile_corpus,
)
from crucible.graph import build_composition_graph
from crucible.ir import digest_payload

CORPUS = 'tests/fixtures/duplicate-names'
CLEAN = 'tests/fixtures/readme-demo'


def test_colliding_names_are_refused_by_default():
    with pytest.raises(ValueError) as caught:
        compile_corpus(CORPUS)
    message = str(caught.value)
    assert 'duplicate skill name(s): copied, shared-name' in message
    assert '--skip-duplicate-names' in message, 'the refusal must name its own opt-in'


def test_explicit_default_matches_the_implicit_one():
    with pytest.raises(ValueError):
        compile_corpus(CORPUS, on_duplicate_name=ON_DUPLICATE_ERROR)


def test_an_unknown_policy_is_refused_before_any_read():
    with pytest.raises(ValueError, match='unsupported on_duplicate_name'):
        compile_corpus(CORPUS, on_duplicate_name='ignore')


def test_skipping_keeps_one_skill_per_name_and_records_the_rest():
    ir = compile_corpus(CORPUS, on_duplicate_name=ON_DUPLICATE_SKIP)
    names = [skill['identity']['name'] for skill in ir['skills']]
    assert names == ['copied', 'shared-name', 'unique']
    assert len(names) == len(set(names))
    assert len(ir['excluded']) == 2


def test_an_identical_republication_is_distinguished_from_a_homonym():
    """Dropping a byte-identical copy loses nothing; dropping a homonym does."""
    ir = compile_corpus(CORPUS, on_duplicate_name=ON_DUPLICATE_SKIP)
    reasons = {entry['name']: entry['reason'] for entry in ir['excluded']}
    assert reasons == {'copied': EXCLUDED_IDENTICAL, 'shared-name': EXCLUDED_DISTINCT}


def test_each_exclusion_names_what_was_dropped_and_what_survived():
    ir = compile_corpus(CORPUS, on_duplicate_name=ON_DUPLICATE_SKIP)
    kept = {skill['identity']['source_path'] for skill in ir['skills']}
    for entry in ir['excluded']:
        assert set(entry) == {
            'name', 'source_path', 'content_digest', 'kept_source_path', 'reason',
        }
        assert entry['source_path'] not in kept
        assert entry['kept_source_path'] in kept
        assert entry['source_path'].startswith('beta/')
        assert entry['kept_source_path'].startswith('alpha/')


def test_which_skill_survives_is_deterministic_not_traversal_order():
    first = compile_corpus(CORPUS, on_duplicate_name=ON_DUPLICATE_SKIP)
    second = compile_corpus(CORPUS, on_duplicate_name=ON_DUPLICATE_SKIP)
    assert first == second
    assert first['artifact_digest'] == second['artifact_digest']


def test_exclusions_are_sealed_into_the_artifact_digest():
    ir = compile_corpus(CORPUS, on_duplicate_name=ON_DUPLICATE_SKIP)
    sealed = {k: v for k, v in ir.items() if k != 'artifact_digest'}
    assert ir['artifact_digest'] == digest_payload(sealed)
    tampered = {**sealed, 'excluded': []}
    assert digest_payload(tampered) != ir['artifact_digest']


def test_a_clean_corpus_still_states_that_it_excluded_nothing():
    """An artifact must never imply complete coverage by omitting the field."""
    ir = compile_corpus(CLEAN)
    assert ir['excluded'] == []
    assert 'excluded' in ir


def test_the_retained_corpus_audits_and_graphs_normally():
    ir = compile_corpus(CORPUS, on_duplicate_name=ON_DUPLICATE_SKIP)
    audit = audit_corpus(ir)
    assert audit['summary']['total'] >= 0
    graph = build_composition_graph(ir, audit)
    assert graph['input_ir_digest'] == ir['artifact_digest']


def test_cli_refuses_a_colliding_corpus_with_a_clean_error(capsys):
    assert main.__module__ == 'crucible.cli'
    import sys
    argv = sys.argv
    try:
        sys.argv = ['crucible', CORPUS, '--no-graph']
        assert main() == 1
    finally:
        sys.argv = argv
    captured = capsys.readouterr()
    assert captured.err.startswith('error: duplicate skill name(s)')
    assert '--skip-duplicate-names' in captured.err
    assert 'Traceback' not in captured.err


def test_cli_flag_analyzes_the_corpus_and_emits_exclusions(capsys):
    import json
    import sys
    argv = sys.argv
    try:
        sys.argv = ['crucible', CORPUS, '--compile-only', '--skip-duplicate-names']
        assert main() == 0
    finally:
        sys.argv = argv
    artifact = json.loads(capsys.readouterr().out)
    assert [entry['name'] for entry in artifact['excluded']] == ['copied', 'shared-name']

"""An unmet precondition must not be reported in the shape of a clean result."""
import json
from pathlib import Path

import pytest

from crucible.auditor import (
    AUDIT_VERSION, OUTCOME_ABSTAINED, OUTCOME_EXERCISED, audit_corpus,
)
from crucible.compiler import compile_corpus
from crucible.graph import build_composition_graph
from crucible.ir import digest_payload

RELATED = '''---
name: {name}
description: {description}
---

# {name}

Retries MUST be bounded for irreversible operations.

## Checks

- Verify the retry bound is enforced.
'''


def write_corpus(root, skills):
    for name, description, body in skills:
        directory = Path(root) / name
        directory.mkdir(parents=True)
        (directory / 'SKILL.md').write_text(body, encoding='utf-8', newline='\n')
    return compile_corpus(root)


def plain(name, description='A skill.'):
    return (name, description, RELATED.format(name=name, description=description))


def audit_of(root, skills):
    return audit_corpus(write_corpus(root, skills))


def test_abstained_check_is_named_with_its_unmet_input(tmp_path):
    audit = audit_of(tmp_path, [plain('alpha'), plain('beta')])
    preconditions = audit['preconditions']
    abstained = {c['check_class']: c for c in preconditions['checks']
                 if c['outcome'] == OUTCOME_ABSTAINED}
    assert 'BROKEN_REFERENCE' in abstained
    entry = abstained['BROKEN_REFERENCE']
    assert entry['requires'] == 'declared_relations'
    assert entry['observed'] == 0
    assert 'no composes_with or delegates_to relation' in entry['reason']
    assert preconditions['abstained_count'] == len(abstained)


def test_every_check_outcome_is_exercised_or_abstained(tmp_path):
    audit = audit_of(tmp_path, [plain('alpha'), plain('beta')])
    for check in audit['preconditions']['checks']:
        assert check['outcome'] in (OUTCOME_EXERCISED, OUTCOME_ABSTAINED)
        assert set(check) == {'check_class', 'requires', 'observed', 'outcome', 'reason'}
        if check['outcome'] == OUTCOME_EXERCISED:
            assert check['reason'] is None
            assert check['observed'] > 0
        else:
            assert check['reason']
            assert check['observed'] == 0


def test_a_declared_relation_moves_relation_checks_to_exercised(tmp_path):
    body = RELATED.format(name='alpha', description='A skill.')
    body += '\n## Composes with\n\n- beta\n'
    ir = write_corpus(tmp_path, [('alpha', 'A skill.', body), plain('beta')])
    checks = {c['check_class']: c for c in audit_corpus(ir)['preconditions']['checks']}
    assert checks['BROKEN_REFERENCE']['outcome'] == OUTCOME_EXERCISED
    assert checks['BROKEN_REFERENCE']['observed'] == 1
    assert checks['ORPHAN_SKILL']['outcome'] == OUTCOME_EXERCISED


def test_orphan_check_abstention_matches_its_own_internal_guard(tmp_path):
    """_check_orphan_skills already refuses to run without an edge.

    That decision was invisible in the artifact. The reported outcome must
    agree with the guard: no relations means no ORPHAN_SKILL findings AND an
    ABSTAINED outcome, never silent emptiness.
    """
    audit = audit_of(tmp_path, [plain('alpha'), plain('beta')])
    checks = {c['check_class']: c for c in audit['preconditions']['checks']}
    assert checks['ORPHAN_SKILL']['outcome'] == OUTCOME_ABSTAINED
    assert not [f for f in audit['findings'] if f['class'] == 'ORPHAN_SKILL']


def test_corpus_inputs_are_whole_numbers_only(tmp_path):
    inputs = audit_of(tmp_path, [plain('alpha'), plain('beta')])['preconditions']['corpus_inputs']
    assert inputs
    for key, value in inputs.items():
        assert type(value) is int, f'{key} is not a whole number'
        assert value >= 0


def test_comparable_pair_counts_match_the_corpus(tmp_path):
    inputs = audit_of(
        tmp_path, [plain('alpha'), plain('beta'), plain('gamma')]
    )['preconditions']['corpus_inputs']
    assert inputs['skills'] == 3
    fingerprinted = inputs['skills_with_fingerprint']
    assert inputs['comparable_skill_pairs'] == fingerprinted * (fingerprinted - 1) // 2


def test_preconditions_are_sealed_into_the_audit_digest(tmp_path):
    audit = audit_of(tmp_path, [plain('alpha'), plain('beta')])
    assert audit['audit_version'] == AUDIT_VERSION == 'crucible-audit/v2'
    sealed = {k: v for k, v in audit.items() if k != 'audit_digest'}
    assert audit['audit_digest'] == digest_payload(sealed)
    tampered = json.loads(json.dumps(sealed))
    tampered['preconditions']['abstained_count'] = 0
    assert digest_payload(tampered) != audit['audit_digest']


def test_preconditions_are_deterministic(tmp_path):
    first = audit_of(tmp_path / 'a', [plain('alpha'), plain('beta')])
    second = audit_of(tmp_path / 'b', [plain('alpha'), plain('beta')])
    assert first['preconditions'] == second['preconditions']
    assert first['audit_digest'] == second['audit_digest']


def test_graph_abstains_when_no_relation_convention_is_used(tmp_path):
    ir = write_corpus(tmp_path, [plain('alpha'), plain('beta')])
    graph = build_composition_graph(ir, audit_corpus(ir))
    assert graph['edges'] == []
    composition = graph['preconditions']['composition']
    assert composition['outcome'] == OUTCOME_ABSTAINED
    assert 'not evidence that this corpus composes cleanly' in composition['reason']
    assert graph['preconditions']['corpus_inputs']['declared_section_relations'] == 0
    assert graph['preconditions']['corpus_inputs']['description_trigger_matches'] == 0


def test_graph_is_exercised_when_a_description_trigger_matches(tmp_path):
    ir = write_corpus(tmp_path, [
        plain('alpha', 'A skill. Sibling of beta.'), plain('beta'),
    ])
    graph = build_composition_graph(ir, audit_corpus(ir))
    assert graph['edges']
    inputs = graph['preconditions']['corpus_inputs']
    assert inputs['description_trigger_matches'] == 1
    assert inputs['resolved_edges'] == len(graph['edges'])
    assert graph['preconditions']['composition'] == {
        'outcome': OUTCOME_EXERCISED, 'reason': None,
    }


def test_an_empty_graph_is_distinguishable_from_an_analyzed_one(tmp_path):
    """The defect this contract closes: both runs used to look identical."""
    silent = build_composition_graph(
        (quiet := write_corpus(tmp_path / 'q', [plain('alpha'), plain('beta')])),
        audit_corpus(quiet),
    )
    analyzed = build_composition_graph(
        (loud := write_corpus(tmp_path / 'l', [
            plain('alpha', 'A skill. Sibling of beta.'), plain('beta'),
        ])),
        audit_corpus(loud),
    )
    assert silent['limitations'] == analyzed['limitations'], 'design limits are static'
    assert silent['preconditions'] != analyzed['preconditions'], 'preconditions must differ'


def test_graph_preconditions_are_sealed(tmp_path):
    ir = write_corpus(tmp_path, [plain('alpha'), plain('beta')])
    graph = build_composition_graph(ir, audit_corpus(ir))
    assert graph['graph_version'] == 'crucible-graph/v2'
    sealed = {k: v for k, v in graph.items() if k != 'graph_digest'}
    assert graph['graph_digest'] == digest_payload(sealed)

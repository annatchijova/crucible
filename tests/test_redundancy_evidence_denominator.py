"""The redundancy evidence must expose how much text was compared.

Fraction reduces, so the exact ratio alone cannot distinguish a coincidence
from a substantive overlap: two identical 58-token fingerprints and a 1-token
pair both print as "1/1", and a pair on the 2/3 threshold could be 2 shared
tokens of 3 or 400 of 600. The raw counts have to be in the evidence.

The second contract here is the coupling: confirm.py parses this prose to
recover the pair, so the format is an interface, not just a message.
"""
import re

import pytest

from crucible.auditor import audit_corpus
from crucible.compiler import compile_corpus
from crucible.confirm import _OTHER_SKILL_RE, _parse_semantic_redundancy_pair

DUPLICATE = '''---
name: {name}
description: Track allergic reactions, identify triggers and prepare a record.
---

# {name}

Reactions MUST be recorded with their suspected trigger.

## Checks

- Verify every recorded reaction names a suspected trigger.
'''


@pytest.fixture
def audit(tmp_path):
    for name in ('allergy-log', 'health-allergy-log'):
        directory = tmp_path / name
        directory.mkdir()
        (directory / 'SKILL.md').write_text(
            DUPLICATE.format(name=name), encoding='utf-8', newline='\n')
    return audit_corpus(compile_corpus(tmp_path))


def redundancy(audit):
    found = [f for f in audit['findings'] if f['class'] == 'SEMANTIC_REDUNDANCY']
    assert found, 'the fixture pair must be reported as redundant'
    return found[0]


def test_evidence_reports_raw_token_counts_not_only_a_reduced_ratio(audit):
    evidence = redundancy(audit)['evidence']
    match = re.search(r'overlap (\d+)/(\d+) tokens \(ratio (\d+)/(\d+)\)', evidence)
    assert match, f'raw counts missing from evidence: {evidence!r}'
    shared, compared, numerator, denominator = (int(g) for g in match.groups())
    assert 0 < shared <= compared
    assert compared >= 10, 'the fixture pair compares more than a handful of tokens'
    # The raw counts must reduce to the reported ratio, so neither can drift.
    from fractions import Fraction
    assert Fraction(shared, compared) == Fraction(numerator, denominator)


def test_identical_fingerprints_do_not_hide_their_size(audit):
    """A reduced ratio of 1/1 is indistinguishable from a one-token pair."""
    evidence = redundancy(audit)['evidence']
    shared, compared = (int(g) for g in
                        re.search(r'overlap (\d+)/(\d+) tokens', evidence).groups())
    if shared == compared:
        assert compared > 1, 'identical fingerprints must still report their size'


def test_the_confirmation_layer_can_still_parse_the_evidence(audit):
    """Invariant: the prose is an interface. Mutation: reword the auditor's
    f-string without updating _OTHER_SKILL_RE -> pair extraction returns None
    and the confirmation layer silently finds no clusters."""
    finding = redundancy(audit)
    assert _OTHER_SKILL_RE.search(finding['evidence']) is not None
    parsed = _parse_semantic_redundancy_pair(finding)
    assert parsed is not None, 'confirm.py could not recover the pair'
    skill_a, skill_b, jaccard = parsed
    assert {skill_a, skill_b} == {'allergy-log', 'health-allergy-log'}
    assert re.fullmatch(r'\d+/\d+', jaccard)

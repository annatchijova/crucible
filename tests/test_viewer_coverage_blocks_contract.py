"""The viewer must show what was NOT analyzed, not only the findings.

Before this, neither UI surface could render preconditions, excluded or
coverage, so the most distinctive honest output of the auditor -- a check
reporting that this corpus gave it nothing to examine -- had no representation
anywhere a reader looks.
"""
import re

import pytest

from crucible.auditor import audit_corpus
from crucible.compiler import ON_DUPLICATE_SKIP, compile_corpus
from crucible.viewer import render_artifact_html

DUPLICATES = 'tests/fixtures/duplicate-names'
CLEAN = 'tests/fixtures/readme-demo'


def text_of(html):
    return re.sub(r'<[^>]+>', ' ', html)


@pytest.fixture
def duplicate_view():
    ir = compile_corpus(DUPLICATES, on_duplicate_name=ON_DUPLICATE_SKIP)
    view = dict(audit_corpus(ir))
    view['excluded'] = ir['excluded']
    view['coverage'] = {'scope': 'local-directory-skills', 'status': 'PARTIAL',
                        'discovered': 5, 'analyzed': 3, 'skipped': 2, 'errors': 0}
    return view


def test_abstained_checks_are_named_with_their_cause(duplicate_view):
    html = render_artifact_html(duplicate_view)
    abstained = [c for c in duplicate_view['preconditions']['checks']
                 if c['outcome'] == 'ABSTAINED']
    assert f'{len(abstained)} abstained on this corpus' in text_of(html)
    for check in abstained:
        assert check['check_class'] in html
        assert check['reason'].split(',')[0][:40] in html


def test_exercised_and_abstained_are_visually_distinguished(duplicate_view):
    html = render_artifact_html(duplicate_view)
    assert 'outcome-abstained' in html
    assert 'outcome-exercised' in html


def test_the_precondition_limitation_travels_with_the_block(duplicate_view):
    """The reader must be told that an abstention is not a clean result."""
    html = render_artifact_html(duplicate_view)
    assert 'not evidence' in text_of(html)


def test_corpus_inputs_are_shown_so_a_low_count_can_be_interpreted(duplicate_view):
    html = render_artifact_html(duplicate_view)
    assert 'rules_with_subject' in html
    assert 'comparable_rule_pairs_by_subject' in html


def test_excluded_distinguishes_a_lost_methodology_from_a_republication(duplicate_view):
    html = render_artifact_html(duplicate_view)
    assert 'DUPLICATE_NAME_DISTINCT_CONTENT' in html
    assert 'DUPLICATE_NAME_IDENTICAL_CONTENT' in html
    body = text_of(html)
    assert 'Excluded skills' in body
    assert 'dropped a distinct' in body


def test_each_exclusion_shows_the_dropped_and_the_kept_path(duplicate_view):
    html = render_artifact_html(duplicate_view)
    for entry in duplicate_view['excluded']:
        assert entry['source_path'] in html
        assert entry['kept_source_path'] in html


def test_partial_coverage_says_findings_cover_a_subset(duplicate_view):
    body = text_of(render_artifact_html(duplicate_view))
    assert 'PARTIAL' in body
    assert 'analyzed subset only' in body
    for key in ('discovered', 'analyzed', 'skipped', 'errors'):
        assert key in body


def test_complete_coverage_does_not_warn(duplicate_view):
    view = dict(duplicate_view)
    view['coverage'] = {'scope': 'local-directory-skills', 'status': 'COMPLETE',
                        'discovered': 3, 'analyzed': 3, 'skipped': 0, 'errors': 0}
    body = text_of(render_artifact_html(view))
    assert 'COMPLETE' in body
    assert 'analyzed subset only' not in body


def test_an_empty_exclusion_list_still_states_that_nothing_was_excluded():
    """Silence must not be mistakable for completeness."""
    ir = compile_corpus(CLEAN)
    view = dict(audit_corpus(ir))
    view['excluded'] = ir['excluded']
    body = text_of(render_artifact_html(view))
    assert 'Excluded skills' in body
    assert 'Every discovered skill was analyzed' in body


def test_design_limitations_are_not_labelled_abstentions():
    """Invariant: the static list is design scope. Mutation: restore the
    "Limitations (Honest Abstentions)" heading -> this goes red, because it
    told every reader of every corpus that checks had abstained."""
    view = dict(audit_corpus(compile_corpus(CLEAN)))
    view['limitations'] = [{'check_class': 'SEMANTIC_REDUNDANCY',
                            'reason': 'by design'}]
    body = text_of(render_artifact_html(view))
    assert 'Honest Abstentions' not in body
    assert 'Documented design limitations' in body
    assert 'the same for every corpus' in body


def test_a_legacy_artifact_without_the_new_blocks_still_renders():
    html = render_artifact_html({
        'audit_version': 'crucible-audit/v1', 'findings': [], 'limitations': [],
        'audit_digest': 'sha256:' + 'a' * 64,
    })
    assert '<html' in html and 'Chain of Custody' in html

"""The demo page at / must not claim a skill passed checks that abstained.

It previously rendered "No findings. The skill(s) passed all 28 checks." for
any clean result. A corpus that yields no findings has not passed every check:
on every real corpus measured, six precondition-dependent checks abstain
because the corpus supplied no input for them.
"""
import re

import pytest

fastapi = pytest.importorskip("fastapi", reason="API extra not installed")

from crucible.api import create_app


@pytest.fixture(scope="module")
def page():
    app = create_app()
    index = next(r for r in app.routes if getattr(r, "path", None) == "/")
    return index.endpoint()


def test_the_page_no_longer_claims_a_clean_skill_passed_every_check(page):
    assert "passed all 28 checks" not in page
    assert "passed all" not in page


def test_a_clean_result_is_qualified_by_the_abstention_count(page):
    assert "No findings were emitted" in page
    assert "abstained on this input" in page
    assert "not evidence that the skill is clean" in page


def test_the_page_renders_preconditions(page):
    assert "function renderPreconditions" in page
    assert "function abstainedChecks" in page
    assert "ABSTAINED" in page
    assert "Why it abstained" in page
    # the limitation text travels with the block rather than being dropped
    assert "pre.limitation" in page


def test_the_page_renders_scan_coverage(page):
    assert "function renderCoverage" in page
    for key in ("discovered", "analyzed", "skipped", "errors"):
        assert key in page
    assert "analyzed subset only" in page


def test_the_page_renders_duplicate_name_exclusions(page):
    assert "function renderExcluded" in page
    assert "DUPLICATE_NAME_DISTINCT_CONTENT" in page
    assert "byte-identical republications" in page


def test_every_rendered_value_goes_through_escaping(page):
    """Skill text is untrusted input rendered into the page."""
    body = page[page.index("function renderPreconditions"):]
    inserted = re.findall(r"escapeHtml\(|\+ (\w+)\.(\w+) \+", body)
    assert "escapeHtml(" in body
    # no renderer interpolates a raw field without escaping it
    assert not re.search(r"\+ (c|e|coverage)\.\w+ \+ '", body), \
        "a field is interpolated without escapeHtml"


def test_abstained_and_exercised_have_distinct_styles(page):
    assert ".outcome-abstained" in page
    assert ".outcome-exercised" in page
    assert ".cov-partial" in page

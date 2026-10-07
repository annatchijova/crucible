# Check-section heading matcher — adjudication follow-up

**Date:** 2026-10-07  **Method:** source review, fixture review, and reading the
held-out skill examples  **Base:** `72a048a`  **Status:** the Example-heading
case remains closed; the broader semantic claim remains unresolved. No code
change was justified by this review.

## Threat model and claim under review

The input is an author-controlled skill document. The compiler extracts
numbered or bulleted lines under selected headings as `checks`; the auditor
then evaluates those extracted items. The question is whether the heading
matcher turns ordinary workflow/example content into verification checks.

The earlier held-out write-ups called `Futures Market Check` in `kalshi` a
false-positive example, while the current compiler comment and regression test
describe similarly shaped headings as legitimate checks. This follow-up checks
that disagreement against the actual source and current code before changing
the rule.

## Findings

### CHECK-HEADING-01 — Example walkthrough headings are excluded

**Level:** CODE FACT, regression covered.

`_extract_checks` skips section titles matching `_EXAMPLE_HEADING`. Existing
tests verify that `Example 3: Fact-checking and verification` yields no
extracted checks and that a non-Example `Futures Market Check` heading still
does. Both focused tests pass. The current code therefore closes that
specific Example-heading route.

### CHECK-HEADING-02 — Whether `Futures Market Check` is a check is not settled

**Level:** PLAUSIBLE HYPOTHESIS, no confirmed bug.

The held-out `kalshi` section is under `Workflows` and lists market retrieval,
sorting, and presentation steps. Reading it supports the hypothesis that it is
a workflow rather than verification criteria. However, the heading explicitly
calls it a “Check.” The compatibility test preserves extraction for this
non-Example title shape but explicitly does not claim semantic ground truth.
Neither substring matching nor the section text alone supplies a stable
ground-truth rule for this distinction.

The earlier claim that this is a confirmed extraction false positive is
therefore too strong. It is an adjudication disagreement and a design question
about what Crucible means by “check.” The prior approximate count of 128
substring-matching headings was not recomputed here and is not evidence that
128 extractions are false positives.

## Disposition

No parser patch is made. A broad title-shape filter risks dropping real
domain-specific headings such as `Live Odds Check`; preserving all titles
containing a check-family word risks extracting ordinary workflow steps.

The operational criterion was then applied as a single-reviewer pilot to 48
current check records associated with check-family headings in 427 source
files: 17 clear checks, 22 workflow steps, 8 reference statements, and 1
abstention. All 14 such records in the sports slice were judged workflow steps
under that criterion; labels are provisional and the sample was already
inspected. The complete source, method, subgroup counts, and limits are in the
[held-out pilot evaluation](../evidence/2026-10-07-check-heading-evaluation.md).

This supports a measurable false-positive hypothesis in the selected slice,
but does not isolate the title matcher from the global verification-starter
path: current IR records do not retain extraction provenance. The next code
increment should expose that provenance, then add fixtures for clear checks,
workflow headings, and incidental title phrases. Keep the broader metric
`CANDIDATE` until that distinction and the one abstention are adjudicated
independently.

## Reproduction

```text
./.venv/bin/python -m pytest -q \
  tests/test_compiler_contract.py::test_example_heading_with_check_vocabulary_is_not_a_checks_section \
  tests/test_compiler_contract.py::test_non_example_heading_with_check_vocabulary_keeps_legacy_extraction
```

Observed: **2 passed**. This establishes the tested extraction behavior, not
semantic correctness for every heading in the held-out corpora.

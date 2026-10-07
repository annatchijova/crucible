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
files: 18 checks, 22 workflow steps, 8 reference statements, and no
abstentions after reviewing the full ONNX source context. All 14 such records
in the sports slice were judged workflow steps
under that criterion; labels are provisional and the sample was already
inspected. The ONNX Example 1 introductory line says to compare outputs,
but the adjacent code uses `np.testing.assert_allclose` with `rtol=1e-3`
and `atol=1e-5`, and
the prose says a mismatch raises. Under the stated operational criterion this
is a CHECK; the earlier ABSTAIN label used only the extracted line and missed
the example's local oracle. This remains a one-reviewer adjudication. Four
source-informed route fixtures now cover a positive and WORKFLOW control for
each extraction route; they characterize existing behavior and do not claim
semantic accuracy. Full counts, source pins, and limits are in the
[held-out pilot evaluation](../evidence/2026-10-07-check-heading-evaluation.md).

This supports a measurable false-positive hypothesis in the selected slice,
but the labels remain provisional. A diagnostic-only `check_trace` now
separates `section-list` from `verification-starter` and records line/title
without changing the IR schema. In this run, 44 of the 48 records came from
the section-list path and 4 from the global starter path; normal persisted IR
still carries no trace field. Adversarial fixture review found that two
same-named `Instructions` headings made the title-keyed section map lose
the first range, so the diagnostic initially reported no title for its
verification-starter record. The trace now follows active headings line
by line while skipping code fences; the repeated-heading regression test
passes. This was a diagnostic metadata defect, not a persisted check or
schema change. The next code increment should add tests for clear checks,
workflow headings, and incidental title phrases. Keep the
semantic claim `CANDIDATE` until the label rule is independently adjudicated.

## Reproduction

```text
./.venv/bin/python -m pytest -q \
  tests/test_compiler_contract.py::test_example_heading_with_check_vocabulary_is_not_a_checks_section \
  tests/test_compiler_contract.py::test_non_example_heading_with_check_vocabulary_keeps_legacy_extraction
```

Observed: **2 passed**. This establishes the tested extraction behavior, not
semantic correctness for every heading in the held-out corpora.

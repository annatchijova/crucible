# Check-heading extraction — held-out pilot evaluation

**Date:** 2026-10-07  **Code base:** `1487b868fbeb0a3c2eca9184aa5d9337e13d1fe5`
**Purpose:** define a falsifiable meaning for a check and measure the current
extractor on a bounded, already-inspected source set before changing it.

## Operational labels

- **CHECK:** an item states an observable condition or gives a verification
  operation whose result can be judged against the behavior or artifact under
  review. A checkbox or an explicit validation criterion qualifies.
- **WORKFLOW:** an item gathers, transforms, or presents information but does
  not state a condition that would make the result correct or incorrect.
- **REFERENCE:** an explanatory or normative fact about a tool/configuration;
  it may be verifiable, but it is not itself an instruction to verify.
- **ABSTAIN:** the source could be a check, but its acceptance criterion is
  missing or cannot be inferred from the text.

The heading alone does not determine the item label. The same rule applies to
titles containing `check`, `verification`, or `validation` and to titles that
do not contain those words.

## Corpus and method

The local review compiled each `SKILL.md` individually with the current
`compile_skill_file` implementation. The set contains all 27 files in
`held-out-sports-skills` at commit
`c5a487da25a883f6ebc0ebb7603e8543409133df`, plus the 400 names in the pinned
TerminalSkills sample (seed `20261004`, 400 of 1,055) at commit
`a021875c0f1bd906248e3784ce470faa65055201`. This is 427 files. The larger
collection scanner was not used because its documented 500-entry limit is
below the complete TerminalSkills checkout size.

We selected the 48 current IR check records whose nearest Markdown heading
contains one of the check-family terms. They occur under 14 skill/heading
pairs. This is a complete count of that selected slice, not a random sample of
all source lines. The repositories and several examples had already been
inspected, so this review consumes the held-out set. Labels below are a single
reviewer's provisional adjudication, not independent expert ground truth.

Some records come from `_extract_checks`'s section-list path and some from its
global verification-starter path. The current IR does not record which path
produced a check. Therefore these counts characterize the returned IR slice;
they do not isolate the causal effect of heading-title matching.

## Results

| Provisional label | Records | Source groups |
|---|---:|---|
| CHECK | 17 | `arcjet` (1, L145); `dns-record-analyzer` (4, L81–84); `pci-dss-compliance` (12, L262–273) |
| WORKFLOW | 22 | Sports workflows: `cricket-data` (3, L78–80), `kalshi` (3, L73–75), `polymarket` (3, L79–81), `sports-news` (2, L59–60), `tennis-data` (3, L56–58); `braintrust` (1, L234); `regression-tester` (6, L43–51); `typescript` compiler-version step (1, L33) |
| REFERENCE | 8 | `envoy` static-configuration notes (5, L130–134); `typescript` CI type-check notes (3, L143–145) |
| ABSTAIN | 1 | `onnx` example comparing outputs without a stated tolerance (1, L123) |
| **Total** | **48** | **14 skill/heading pairs** |

| Corpus slice | CHECK | WORKFLOW | REFERENCE | ABSTAIN | Total |
|---|---:|---:|---:|---:|---:|
| Sports skills | 0 | 14 | 0 | 0 | 14 |
| TerminalSkills sample | 17 | 8 | 8 | 1 | 34 |

The current output labels all 48 records as `checks`. Under the provisional
criterion, 17/48 (35.4%) are clear checks, 30/48 (62.5%) are clear workflow or
reference material, and one is unresolved. If the unresolved case is a check,
the corresponding share is 18/48 (37.5%). These are counts in this selected,
consumed slice, not corpus-wide precision or recall estimates. No confidence
interval is reported because the records are not a probability sample and
labels have one reviewer. Recall is not measured: the review did not enumerate
all sections or lines that the current extractor omitted.

The current regression controls both pass: an `Example N:` heading with
check-family words is not extracted through the section-list path, and a
non-Example check heading is still recognized. These tests confirm those
specific behaviors; they do not establish that every retained heading is a
check. The additional Example records in this scan were produced by the global
verification-starter path, showing why extraction provenance must be visible
before attributing every false positive to the heading matcher.

## Decision and next measurable step

This pilot establishes a usable labeling criterion and a concrete error
surface, but it does not support a safe rule patch yet. First add extraction
provenance to the IR (`section-list` vs `verification-starter`) and preserve
the relevant heading path. Then turn the clear examples above into negative
and positive fixtures, adjudicate the single abstention independently, and
rerun the same pinned set as a spent validation set. Keep a new corpus or
shard untouched for a later evaluation. Do not claim a general precision or
recall improvement from this pilot alone.

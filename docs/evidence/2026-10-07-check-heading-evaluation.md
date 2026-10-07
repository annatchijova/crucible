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

The persisted IR does not record the extraction path. A private diagnostic
parameter now records `section-list` vs `verification-starter` plus source
line and nearest section title; it does not alter the persisted IR shape.
The traced extractor and ordinary `compile_skill_file` output were compared
for all 427 files and returned identical check records.

## Results

| Provisional label | Records | Source groups |
|---|---:|---|
| CHECK | 18 | `arcjet` (1, L145); `dns-record-analyzer` (4, L81–84); `pci-dss-compliance` (12, L262–273); `onnx` Example 1 (1, L123 + local code) |
| WORKFLOW | 22 | Sports workflows: `cricket-data` (3, L78–80), `kalshi` (3, L73–75), `polymarket` (3, L79–81), `sports-news` (2, L59–60), `tennis-data` (3, L56–58); `braintrust` (1, L234); `regression-tester` (6, L43–51); `typescript` compiler-version step (1, L33) |
| REFERENCE | 8 | `envoy` static-configuration notes (5, L130–134); `typescript` CI type-check notes (3, L143–145) |
| ABSTAIN | 0 | none after source-level review of the ONNX example |
| **Total** | **48** | **14 skill/heading pairs** |

| Corpus slice | CHECK | WORKFLOW | REFERENCE | ABSTAIN | Total |
|---|---:|---:|---:|---:|---:|
| Sports skills | 0 | 14 | 0 | 0 | 14 |
| TerminalSkills sample | 18 | 8 | 8 | 0 | 34 |

| Extraction route | CHECK | WORKFLOW | REFERENCE | ABSTAIN | Total |
|---|---:|---:|---:|---:|---:|
| `section-list` | 16 | 20 | 8 | 0 | 44 |
| `verification-starter` | 2 | 2 | 0 | 0 | 4 |

The current output labels all 48 records as `checks`. Under the provisional
criterion, 18/48 (37.5%) are checks and 30/48 (62.5%) are workflow or
reference material. The ONNX Example 1 record is classified as CHECK after
reviewing its full context: the adjacent code calls `np.testing.assert_allclose`
with `rtol=1e-3` and `atol=1e-5`, and the text states that a mismatch raises.
The introductory sentence at L123 omits that criterion, but the complete
instruction/example supplies it. This is a single-reviewer adjudication, not
independent ground truth. These are counts in this selected,
consumed slice, not corpus-wide precision or recall estimates. No confidence
interval is reported because the records are not a probability sample and
labels have one reviewer. Recall is not measured: the review did not enumerate
all sections or lines that the current extractor omitted.

## Route fixtures and adjudication

Four source-informed fixtures now characterize each extraction route with a
CHECK positive and a WORKFLOW negative control. The test asserts exact text,
route, and section title; it does not implement or validate a semantic
classifier. The two negative controls are expected to be emitted by today's
extractor, making the semantic gap visible rather than hiding it. They are
development fixtures, not an independent or held-out evaluation set.

| Route | Fixture | Provisional label | Reason |
|---|---|---|---|
| `section-list` | `Validation Criteria` / exact response status | CHECK | Observable condition with a judgeable value |
| `section-list` | `Live Odds Check` / search markets | WORKFLOW | Data gathering without an acceptance condition |
| `verification-starter` | Verify detached signature against publisher key | CHECK | Direct operation with a determinate comparison |
| `verification-starter` | Run export and print artifact path | WORKFLOW | Execution/presentation only |

The ONNX example was separately adjudicated CHECK from its full source context,
including the executable tolerance assertion; retain the single-reviewer
qualification above.

Existing regression controls pass: an `Example N:` heading with
check-family words is not extracted through the section-list path, and a
non-Example check heading keeps its existing extraction behavior. These tests
confirm those specific behaviors; they do not establish that every retained
heading is a check. Two Example records in this set were instead produced by
the global verification-starter path.

## Decision and next measurable step

This pilot establishes a usable criterion and error surface, but the labels
remain single-reviewer and do not support a safe semantic rule patch. The
diagnostic trace now separates the two extraction routes without changing
serialized data. The next step is independent review of the source-informed
route fixtures and repeated evaluation on a fresh pinned corpus. Reuse this
set only as
spent validation; reserve a new corpus or shard for later evaluation. Do not
claim general precision or recall from this pilot.

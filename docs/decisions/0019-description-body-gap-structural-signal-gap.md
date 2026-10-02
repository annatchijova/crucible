# ADR-0019: Description-Body Gap — Procedural-Structure False-Positive Finding

**Status:** Implemented — Option B, both parts done
**Date:** 2026-10-02 (measurement); decision 2026-10-02; part 2 implemented
2026-10-02
**Reversibility:** high; the implementation plan below is now fully carried
out in `compiler.py`/`auditor.py`, both parts verified against the real
corpus

## Context

ADR-0014 accepted DESCRIPTION_BODY_GAP against the author's own ~97-skill
corpus (27/97 = 28% CANDIDATE rate) and explicitly deferred extending the
L1 extractor to capture non-RFC-2119 normative language, naming that as
the likely source of false positives: "Either the extractor needs to be
extended to capture non-RFC-2119 normative language, or these skills
genuinely lack normative structure. The check cannot distinguish the two
cases."

Running the same check against a large, independently-written external
corpus (github.com/mukul975/Anthropic-Cybersecurity-Skills, 818 skills)
makes that deferred question answerable with real evidence instead of
speculation.

This measurement was run after fixing two unrelated compiler bugs found on
the same corpus (a shell comment inside a code fence misread as a Markdown
heading; a verb-list drift between check-extraction and oracle_kind
classification — see `docs/evidence/2026-10-02-mukul975-corpus-audit/
FINDINGS.md`, Findings 0 and 0b). The DESCRIPTION_BODY_GAP count moved
across each fix (179 -> 188 -> 177, as skills gained or lost fabricated/
newly-recognized checks), but the 100% false-positive conclusion below
held at every measurement and is not an artifact of either compiler bug.

## What was measured

177/818 skills (22%) were flagged DESCRIPTION_BODY_GAP (post compiler
fix). Every flagged
skill's body was classified by whether it contains real structural
content beyond this corpus's universal boilerplate sections (`Overview`,
`When to Use`, `Prerequisites`, `References`, `Key Concepts`) — either
2+ non-boilerplate section headings (e.g. `Running Hindsight`, `Key
Artifact Files`, `Validation Criteria`) or 2+ numbered `### Step N:`
sections. Full method and per-skill classification:
`docs/evidence/2026-10-02-mukul975-corpus-audit/FINDINGS.md` and
`dbg_classification.json` in the same directory.

**Result: 177/177 (100%) have real procedural/workflow structure. Zero are
genuinely thin or empty.** A hand-verified sample
(`analyzing-cobalt-strike-beacon-configuration`,
`analyzing-browser-forensics-with-hindsight`) confirmed the automated
classification: Prerequisites, numbered or domain-specific sections,
runnable code blocks, reference tables, and (where present) an explicit
validation-criteria checklist — written entirely in plain imperative
English, never RFC-2119 modals.

A sanity check against a deliberately empty fixture (a skill with a
substantive description and a body of unstructured prose, no headings, no
steps) confirms the check still correctly fires on a real gap — this is
not a broken or useless check, it has a real, now-quantified scope
limitation against one common authoring style.

## The decision this ADR is for

ADR-0014 already correctly identified the two possible readings of a
DESCRIPTION_BODY_GAP hit ("extractor scope gap" vs. "genuine gap") and
left the check as CANDIDATE specifically because it could not distinguish
them. This measurement resolves that uncertainty for this corpus and style:
on a corpus dominated by numbered-step/reference-table-style skills, it is
overwhelmingly an extractor scope gap, not a genuine content gap. That
does not mean the check is wrong on every corpus (the author's own 28%
rate from ADR-0014 was never independently classified the same way, and
may contain more genuine gaps) — but it does mean the deferred question
from 2026-09-23 is no longer speculative where this corpus is concerned.

Two live options were presented:

**Option A — leave DESCRIPTION_BODY_GAP exactly as specified in ADR-0014.**
Keep it a strict RFC-2119-structure check and document, per corpus, what
fraction of hits are this style-driven false positive. Honest and simple,
but the check becomes close to useless as a standalone signal on corpora
that favor numbered-step or reference-table style over RFC-2119
phrasing — a large and common authoring convention, not a rare edge case.

**Option B — add a second, independently-justified structural signal.**
Extend L1's extraction (not DESCRIPTION_BODY_GAP's logic directly) to
recognize procedural structure as a distinct kind of extractable content,
separate from RFC-2119 rules.

## Decision: Option B (2026-10-02)

Anna chose Option B explicitly, accepting that it is the larger, slower,
more bug-prone path: "Sé que es más compleja, pero es la correcta." This
section records the concrete design, refined with real measurement taken
*before* writing any code, per this ADR's own prior warning that the
scope question ("what counts as structured") needs a committed, tested
definition, not an ad hoc one.

### A load-bearing discovery that changes the shape of the fix

`procedural_steps` **already exists** in the L1 IR, extracted by
`_extract_procedural_steps`. Its section-title filter
(`_PROCEDURAL_SECTIONS = {"steps", "procedure", "how to", "how",
"process", "workflow", "method"}`) checks for the substring `"steps"`
(plural). This corpus's dominant heading convention is `### Step 1:
Title` (singular, followed by a number) — which never contains the
substring `"steps"` and is therefore **invisible to the existing
extractor today**, independent of DESCRIPTION_BODY_GAP entirely. Verified
by induction: `analyzing-cobalt-strike-beacon-configuration` has 0 rules,
0 checks, AND 0 procedural_steps despite having four real numbered Step
sections with runnable code — the heading-matching gap, not a missing
category of IR field, is the direct cause.

This means Option B does **not** require inventing a new IR field or a
new kind of "structural signal" the way the original framing above
suggested. It requires fixing a real, narrower gap in the *existing*
`procedural_steps` extractor, after which DESCRIPTION_BODY_GAP's existing
logic (`if rules or checks or steps: continue`) starts correctly
suppressing the false positive on its own, with no change to
`_check_description_body_gap` itself.

### The two-part design, each independently measured

Re-classifying all 177 DESCRIPTION_BODY_GAP hits by which signal would
resolve them:

| Signal | Skills resolved | Share |
|---|---|---|
| A `### Step N: Title` heading recognized as one procedural step (the heading text itself is the step, since the step's content is often a fenced code block, not a bullet/numbered list under it) | 137 | 77% |
| No Step-N heading at all; needs a second signal — a minimum count of non-boilerplate section headings (e.g. `## Running Hindsight`, `## Key Artifact Files`) counted as procedural content | 40 | 23% |

Both signals are needed; neither alone covers the corpus. The second
signal is weaker and more judgment-laden (what counts as "boilerplate"
is exactly the ad hoc risk this ADR already flagged) and should get the
more careful negative-control testing of the two.

### Implementation plan

1. **Step-N heading recognition** — **DONE 2026-10-02.** Implemented as a
   fourth extraction path directly in `_extract_procedural_steps` (scans
   `lines` with the same `_HEADING` + `code_lines` exclusion every other
   path in the file already uses, rather than going through
   `_section_ranges`'s lowercased title dict — needed the heading's
   original casing for the extracted step text). New
   `_STEP_HEADING` regex: `^step\s+\d+[a-z]?\b[:\-–—.\s]*(?P<title>.*)$`,
   case-insensitive, anchored at the start of the heading's own title
   (not a substring match). A corpus survey of all 2,908 real `Step N`
   headings found separators `:` (2768), em-dash (108), and a literal
   `---` (20), plus lettered sub-steps (`Step 2a:`, 18) — all covered.
   Falls back to the full heading text when no descriptive suffix follows
   the number (a bare `### Step 3`), rather than dropping the step. Four
   regression tests, including the exact false-positive guards this plan
   named (`## Next Steps to Consider`, `## Steps Overview` do not match).
   **Result: `DESCRIPTION_BODY_GAP` 177 -> 40, matching the 137-skill
   prediction exactly.** Full writeup, including a checked secondary
   effect on two other checks that now correctly see previously-invisible
   steps, in `docs/evidence/2026-10-02-mukul975-corpus-audit/FINDINGS.md`
   ("Finding 2 follow-up").
2. **Non-boilerplate heading count** — **DONE 2026-10-02.** Placed as a
   new, separately named IR field (`structural_headings`), not folded
   into `_extract_procedural_steps` — a reference-style section heading
   ("Running Hindsight", "MFT Structure and Record Layout") is not a
   step, and mislabeling it as one would have been a false simplification.
   New `_extract_structural_headings` function (`compiler.py`) collects
   non-boilerplate, non-title, non-code-fence level->=2 headings per
   skill. `_BOILERPLATE_SECTIONS` (`compiler.py`) is the committed
   constant: `{overview, when to use, prerequisites, references, key
   concepts}` — measured against the 40 skills still flagged after part
   1: `overview`/`when to use`/`prerequisites` in 40/40, `references` in
   36/40; `key concepts` carried over from ADR-0014's original list.
   `_check_description_body_gap` (`auditor.py`) suppresses the finding
   when `len(structural_headings) >= _MIN_STRUCTURAL_HEADINGS` (2),
   alongside the existing rules/checks/steps test. Measured before
   implementing: every one of the 40 remaining skills has >=2
   non-boilerplate headings (minimum observed: 2); zero skills anywhere
   in the 818-skill corpus have 0 or 1 — meaning no real negative control
   exists in the live corpus, exactly the risk this ADR's own rejected
   alternative ("count any heading as structured") warned about. A
   synthetic negative control (a skill with only the four boilerplate
   headings and prose, no other structure) was written as a test and
   confirmed the check still fires. **Result: `DESCRIPTION_BODY_GAP`
   40 -> 0** on mukul975/Anthropic-Cybersecurity-Skills; 0 on the
   author's own corpus (was already 0 there). 8 new tests (4 compiler-
   level for `structural_headings` itself, 4 check-level including the
   negative control and the below-threshold guard).
3. Re-run both fixes against mukul975/Anthropic-Cybersecurity-Skills AND
   the author's own corpus — **DONE**, see result above; no other check
   that should stay CANDIDATE was flipped.
4. Full regression + mutation-gate pass — **DONE**, both green.

This is expected to take real time and surface its own bugs along the
way (per Anna's own expectation going in) — not a one-session fix like
the prior three compiler bugs.

## Alternatives rejected (for the measurement itself)

- **Requiring a fenced code block alongside Step headings.** The first
  classification pass used this (against an earlier, pre-Finding-0b count
  of 179 flagged skills) and left 34 unclassified; manual review showed
  these were
  equally structured, just organized around domain-specific headings
  (`Running Hindsight`, `Browser Profile Locations`) rather than
  `Step N:`. Rejected as too narrow — see `FINDINGS.md` for the specific
  examples that motivated broadening it.
- **Counting any heading as "structured."** Would trivially classify
  every skill as structured (all 818 have at least `Overview`/`When to
  Use`), making the measurement meaningless. The boilerplate-exclusion
  list is load-bearing for the measurement to mean anything.

## Consequences

Accepted now:
- DESCRIPTION_BODY_GAP's false-positive rate against a numbered-step/
  reference-table-style corpus is quantified at 100% (177/177), not
  estimated or assumed.
- The sanity check confirms the detector logic itself is not broken — it
  correctly flags a deliberately empty fixture.
- `docs/evidence/2026-10-02-mukul975-corpus-audit/dbg_classification.json`
  exists for independent re-verification of the classification.
- Option B is the chosen direction; both parts of the implementation plan
  (Step-N heading recognition, then the non-boilerplate heading-count
  signal) are implemented, tested, and verified against the real corpus.
  `DESCRIPTION_BODY_GAP` went 177 -> 40 -> 0 on mukul975/Anthropic-
  Cybersecurity-Skills across the two parts; 0 on the author's own corpus
  throughout.

Deferred:
- Applying the same structural-signal classification method to the other
  remaining large CANDIDATE classes on this corpus (MISSING_FAILURE_MODE
  61, SCOPE_TRIGGER_MISMATCH 54, CHECK_WITHOUT_ORACLE 27, REQUIREMENT_
  WITHOUT_CHECK 34) to check whether they share the same style-driven
  false-positive pattern. Not started.

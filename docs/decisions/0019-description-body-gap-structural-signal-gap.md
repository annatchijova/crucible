# ADR-0019: Description-Body Gap — Procedural-Structure False-Positive Finding

**Status:** Accepted — Option B
**Date:** 2026-10-02 (measurement); decision 2026-10-02
**Reversibility:** high; no code changed by this record, it only documents a
measurement and the chosen design for implementation

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
2. **Non-boilerplate heading count** (new, narrower rule — exact
   placement TBD: inside `_extract_procedural_steps` as a second path, or
   a new, separately named IR signal if steps-semantics turn out not to
   fit): define the boilerplate exclusion list as a committed, named
   constant (not inferred per-run), require a stated minimum count
   (measurement above used >=2), and write negative controls proving a
   skill with only boilerplate headings and no real content does NOT
   get promoted.
3. Re-run both fixes against mukul975/Anthropic-Cybersecurity-Skills AND
   the author's own corpus, confirm the DESCRIPTION_BODY_GAP count drops
   as predicted without flipping any check that should stay CANDIDATE
   (e.g. a skill with real RFC-2119 rules and zero steps of either kind
   must still be flagged).
4. Full regression + mutation-gate pass before considering this closed,
   same discipline as every other fix this session.

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
- Option B is the chosen direction; the implementation plan above (Step-N
  heading recognition, then the non-boilerplate heading-count signal) is
  the committed design, not yet implemented.

Deferred, pending implementation:
- The actual code change to `_extract_procedural_steps` and its test
  suite/negative controls.
- Applying the same structural-signal classification method to the other
  remaining large CANDIDATE classes on this corpus (MISSING_FAILURE_MODE
  53, SCOPE_TRIGGER_MISMATCH 54, CHECK_WITHOUT_ORACLE 27, the remaining 34
  REQUIREMENT_WITHOUT_CHECK post-Finding-0b) to check whether they share
  the same style-driven false-positive pattern.

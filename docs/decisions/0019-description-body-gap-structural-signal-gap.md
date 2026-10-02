# ADR-0019: Description-Body Gap — Procedural-Structure False-Positive Finding

**Status:** Proposed
**Date:** 2026-10-02
**Reversibility:** high; no code changed by this record, it only documents a
measurement and proposes options

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

This measurement was run after fixing an unrelated compiler bug found on
the same corpus (a shell comment inside a code fence was misread as a
Markdown heading, corrupting check/step/relation extraction corpus-wide —
see `docs/evidence/2026-10-02-mukul975-corpus-audit/FINDINGS.md`, Finding
0). The DESCRIPTION_BODY_GAP count shifted slightly after that fix (179 ->
188, since some skills that previously had fabricated "checks" correctly
lost them); the 100% false-positive conclusion below held across both
measurements and is not an artifact of the compiler bug.

## What was measured

188/818 skills (23%) were flagged DESCRIPTION_BODY_GAP (post compiler
fix). Every flagged
skill's body was classified by whether it contains real structural
content beyond this corpus's universal boilerplate sections (`Overview`,
`When to Use`, `Prerequisites`, `References`, `Key Concepts`) — either
2+ non-boilerplate section headings (e.g. `Running Hindsight`, `Key
Artifact Files`, `Validation Criteria`) or 2+ numbered `### Step N:`
sections. Full method and per-skill classification:
`docs/evidence/2026-10-02-mukul975-corpus-audit/FINDINGS.md` and
`dbg_classification.json` in the same directory.

**Result: 188/188 (100%) have real procedural/workflow structure. Zero are
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

Two live options, not yet chosen:

**Option A — leave DESCRIPTION_BODY_GAP exactly as specified in ADR-0014.**
Keep it a strict RFC-2119-structure check and document, per corpus, what
fraction of hits are this style-driven false positive (as this ADR now
does for mukul975/Anthropic-Cybersecurity-Skills). Honest and simple, but
the check becomes close to useless as a standalone signal on corpora that
favor numbered-step or reference-table style over RFC-2119 phrasing — a
large and common authoring convention, not a rare edge case.

**Option B — add a second, independently-justified structural signal.**
Extend L1's extraction (not DESCRIPTION_BODY_GAP's logic directly) to
recognize numbered procedural sections and/or a minimum count of non-
boilerplate section headings as a distinct kind of extractable structure,
separate from RFC-2119 rules. A skill with this structure would no longer
trigger DESCRIPTION_BODY_GAP (though it might still be a candidate for a
new, narrower check that asks different questions about procedural
skills — e.g. whether referenced tools/commands are pinned, whether steps
have an explicit success condition). This directly reduces the measured
false-positive rate but changes what DESCRIPTION_BODY_GAP's CANDIDATE
status actually means, and needs its own falsifiable test suite and
negative controls (an extractor loosened to catch "Step N:" headings must
not start accepting skills that merely have *any* heading as
"structured" — the boilerplate exclusion list in the measurement above is
exactly the kind of judgment call that needs a committed, tested
definition, not an ad hoc one).

This ADR does not choose between them — that choice should be made
explicitly (updating this ADR to Accepted with the chosen option) before
any extractor code changes, per this project's own discipline of deciding
before implementing.

## Alternatives rejected (for the measurement itself)

- **Requiring a fenced code block alongside Step headings.** The first
  classification pass used this and left 34/188 skills unclassified
  (correctly) as not yet accounted for; manual review showed these were
  equally structured, just organized around domain-specific headings
  (`Running Hindsight`, `Browser Profile Locations`) rather than
  `Step N:`. Rejected as too narrow — see `FINDINGS.md` for the specific
  examples that motivated broadening it.
- **Counting any heading as "structured."** Would trivially classify
  every skill as structured (all 818 have at least `Overview`/`When to
  Use`), making the measurement meaningless. The boilerplate-exclusion
  list is load-bearing for the measurement to mean anything.

## Consequences

Accepted now (the measurement itself, independent of which option is
chosen):
- DESCRIPTION_BODY_GAP's false-positive rate against a numbered-step/
  reference-table-style corpus is quantified at 100% (188/188), not
  estimated or assumed.
- The sanity check confirms the detector logic itself is not broken — it
  correctly flags a deliberately empty fixture.
- `docs/evidence/2026-10-02-mukul975-corpus-audit/dbg_classification.json`
  exists for independent re-verification of the classification.

Deferred, pending Option A/B decision:
- Any change to L1's extractor or to DESCRIPTION_BODY_GAP's logic.
- Applying the same structural-signal classification method to the other
  large CANDIDATE classes on this corpus (REQUIREMENT_WITHOUT_CHECK 70,
  MISSING_FAILURE_MODE 55, SCOPE_TRIGGER_MISMATCH 54, CHECK_WITHOUT_ORACLE
  27 post-fix) to check whether they share the same style-driven
  false-positive pattern.

# Normative-rule extraction yields almost nothing on an external corpus

**Date:** 2026-10-23  **Branch:** `main`  **Base:** `094a087`
**Scope:** local compiler and auditor on two real corpora. No model involved.
**Status:** reproduced; no fix applied. This record bounds a published claim.

## Question

`docs/COMPETITIVE_BOUNDARY.md` lists three capabilities as
`VERIFIED DIFFERENTIATOR, implementation pending`: normative rule extraction,
`MUST`/`MUST NOT`/`SHOULD` semantics, and requirement-to-check mapping. All
three rest on the same artifact: the normative rules the compiler extracts
into the Skill IR. What do they yield on skills the author did not write?

## Firstness — what was observed

Same compiler, same base commit, two corpora:

| Measure | author (101 skills) | mukul975 @ `54a7988` (818 skills) |
|---|---|---|
| rules extracted | 191 | 221 |
| rules per skill | 1.89 | **0.27** |
| skills with at least one rule | 55 / 101 (54%) | 143 / 818 (17%) |
| rules with a `subject` | 22 (12%) | **1 (0.5%)** |
| `MUST` + `MUST_NOT` rules | 99 | **2** |
| `IMPERATIVE` rules (non-modal fallback) | 19 (10%) | 191 (**86%**) |
| checks extracted | 240 (2.38/skill) | 2206 (2.70/skill) |
| procedural steps | 676 | 8228 |

Modality distribution on the external corpus: `IMPERATIVE` 191, `NEVER` 14,
`ALWAYS` 14, `MUST` 1, `MUST_NOT` 1.

## Secondness — how this deviates from the expected baseline

The expected baseline for a modality-aware rule IR is that real skills state
obligations with modal keywords. The author corpus matches that expectation:
`MUST` 54, `MUST_NOT` 45, `NEVER` 36, `SHOULD` 21.

The external corpus does not. Across 818 independently authored security
skills, the extractor found **two** rules using `MUST` or `MUST_NOT`, and 86%
of what it did classify as rules fell through to the non-modal `IMPERATIVE`
bucket. Check and step extraction, by contrast, performed comparably on both
corpora (2.70 vs 2.38 checks per skill). The deficit is specific to the
normative-rule layer, not to extraction generally.

## Thirdness — the general rule

Every downstream capability that consumes a rule `subject` is therefore inert
on this corpus, and the inertness is silent:

- `_check_normative_conflict` groups rules by `subject` and compares pairs
  within each group. With 1 subject in 818 skills, it compares **0 pairs**.
- `_check_conditional_contradiction` filters an all-rule pair loop by equal
  `subject`. It also compares **0 pairs**.
- `REQUIREMENT_WITHOUT_CHECK` emitted 23 findings over 818 skills, against 24
  over 101 author skills, consistent with a rule-count ceiling rather than
  with coverage quality.

The law:

> Crucible's normative-rule layer is calibrated to the author's own writing
> conventions. On skills written without explicit modal keywords it extracts
> almost no rules and almost no subjects, so every differentiator built on
> that layer produces no output, while the artifact reports the absence of
> output in the same shape as a clean result.

Taken with the 0-edge composition result in
[the composition record](../2026-10-23-composition-silent-on-external-corpus/FINDINGS.md),
the consequence for the 1056 findings on this corpus is direct:
`COMMAND_ORACLE_WITHOUT_ARTIFACT` (559) and `CHECK_WITHOUT_ORACLE` (326) are
84% of the total, and both operate on extracted `checks`, which require
neither a modality nor a subject nor an edge. The output on an external
corpus is produced almost entirely by generic pattern checks -- the part of
the capability matrix already marked as overlapping existing tooling.

## Refutation attempted

Three benign hypotheses were tested against the evidence.

1. *The external corpus is simply not normative.* Partly true and
   insufficient: 8228 procedural steps and 2206 checks were extracted from it,
   so the text is instruction-dense. A corpus of 818 security procedures that
   genuinely contains two obligations is less plausible than an extractor
   keyed to vocabulary its authors did not use.
2. *The corpus is unrepresentative.* Not refuted, and it limits the claim: one
   corpus cannot establish a base rate for modal-keyword usage. The claim here
   is bounded to it, and the needed evidence is two further corpora the author
   has not consumed.
3. *The author corpus is the intended target and this is by design.* Refuted
   by `COMPETITIVE_BOUNDARY.md`, which offers these three capabilities as
   differentiators against NVIDIA tooling operating on published catalogs, not
   as author-corpus features.

## Defects recorded

| ID | Defect | Evidence | Claim affected |
|---|---|---|---|
| R-01 | 0.27 rules per skill and 2 modal rules across 818 real skills; 86% fall through to `IMPERATIVE` | table above | `MUST`/`MUST NOT`/`SHOULD` semantics as a differentiator |
| R-02 | `subject` extraction yields 1 of 818, silently disabling both pairwise rule checks | 0 pairs compared in each | normative conflict and conditional contradiction |
| R-03 | Zero rule yield is reported identically to a clean audit; no abstention names the unmet precondition | audit artifact carries no rule-yield signal | honest degradation, `CLAUDE.md` section 5.3 |

R-03 is the same defect class as C-01 in the composition record: a
precondition the corpus did not satisfy is reported as an absence of problems.

## Limits of this record

- Two corpora, one authored by the project author, one already consumed for
  compiler fixes on 2026-10-02. No base rate, no recall estimate, no corpus
  precision.
- Rule, check and step counts are extractor output, not adjudicated ground
  truth. Nothing here establishes that the 221 extracted rules are correct or
  that the unextracted obligations are real obligations.
- No fix is proposed. Widening the modal vocabulary would change finding
  counts on a corpus already used for tuning, which is exactly the move the
  tuning/held-out separation exists to prevent. The fix belongs after a fresh
  held-out corpus is sealed.

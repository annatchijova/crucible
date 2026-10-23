# Adjudication frame over held-out findings

**Date:** 2026-10-23  **Branch:** `main`
**Frame digest:** `sha256:ab41aaa0980aad01852fb7f59037cd7089fad979b8a62230efa03d4de9196154`
**State:** `UNLABELED`. No finding has been adjudicated.

## The question this serves

"What proportion of candidate findings survive adjudication?" is the first of
the four measurements an external review asked for. It is also the one most
easily answered dishonestly, in three ways this frame is built to prevent.

**Choosing what to judge after seeing the answers.** The selection is fixed
and sealed before any judging, and is reproducible: inside each stratum,
findings are ordered by SHA-256 of a stable key and the first *k* are taken.
Re-running `build_frame.py` on the same commits reproduces the same frame
digest, verified across two runs.

**Pooling denominators.** The strata differ in population by two orders of
magnitude, from 1 to 239. A single pooled precision figure would mostly
measure whichever class the auditor emits most. `validate_adjudication.py`
reports per stratum and never pools.

**Reporting an estimate as if it were exact.** A stratum where the target
covers the whole population is a `CENSUS` and its proportion is exact over
that population. A stratum where it does not is a `SAMPLE`, and its proportion
is an estimate with no interval available from this frame. Every reported
stratum carries which it is.

## The frame

Built over the two `HELDOUT_SEALED` corpora only, because a precision claim is
a generalization claim and the other two corpora are consumed. 1015 findings,
28 strata, 192 selected at a per-stratum target of 10, of which 15 strata are
a census and 13 a sample.

| Target *k* | Findings to judge | Census strata | Sample strata |
|---|---|---|---|
| 5 | 110 | 11 | 17 |
| **10** | **192** | **15** | **13** |
| 20 | 307 | 18 | 10 |

The two largest strata are where the answer actually matters:
`REQUIREMENT_WITHOUT_CHECK` (239 + 62 = 301 findings) and
`COMMAND_ORACLE_WITHOUT_ARTIFACT` (229 + 44 = 273) are 57% of the 1015. At
k=10 both stay samples in both corpora, so a precision figure for them will be
an estimate from 10 of 239 and 10 of 62. Raising *k* buys precision exactly
where it is scarcest and nowhere else.

[`frame.json`](frame.json) carries every stratum and selection.
[`response-template.json`](response-template.json) carries one blank row per
selected finding.

## Outcomes a reviewer may record

`CONFIRMED`, `REJECTED`, `UNRESOLVED`. The third exists so a reviewer is never
forced into a binary answer, matching `CLAUDE.md` section 5.3 and the coverage
rubric's own `UNRESOLVED`. `CONFIRMED` and `REJECTED` must quote the source
they rest on; every outcome needs a rationale.

## What is deliberately not in the committed frame

The frame carries `finding_id`, `skill`, `source_path`, `source_span`,
`source_file_digest`, `rule_id` and the selector. It carries **no** auditor
`evidence` string, because `SCOPE_TRIGGER_MISMATCH` evidence embeds tokens
extracted from the skill, and the 27-day plan requires source-derived material
to stay private until per-skill licensing is cleared. Skill names and paths
follow the precedent already set by the committed corpus-provenance records
and the 2026-10-02 adjudication record.

The reviewer's working copy, which does carry evidence strings, is written as
`reviewer-material.PRIVATE.json` beside the frame and is excluded by
`.gitignore`.

## Validator negative controls

Eight adversarial submissions, built from synthetic responses kept outside the
repository:

| Submission | Result |
|---|---|
| outcome `PROBABLY` | exit 1, `outcome 'PROBABLY' is not allowed` |
| `frame_digest` rebound | exit 1, `response is not bound to this frame digest` |
| `authenticity_status` raised to `VERIFIED` | exit 1, `no reviewer trust root exists` |
| `CONFIRMED` with no source quote | exit 1, `CONFIRMED must quote the source it rests on` |
| whitespace rationale | exit 1, `a rationale is required` |
| one selected finding deleted | exit 1, `assessments do not match the frame selection order` |
| frame `population` edited after sealing | exit 1, `frame digest mismatch` |
| same `reviewer_label` twice | exit 1, `both responses carry the same reviewer_label` |

Two well-formed synthetic responses produced per-stratum counts with `CENSUS`
and `SAMPLE` labelled correctly, confirmed-of-decided reported as an `n/d`
ratio rather than a rounded decimal, and 128 disagreements listed individually
as `UNRESOLVED pending a separately recorded third review`.

## Limits

- A frame is not evidence. Nothing here measures precision; it records what a
  reviewer will be asked.
- Selection is deterministic pseudo-random, not a documented probability
  sample. It is unrelated to whether a finding is correct, which is what makes
  it usable, but it supports no sampling theory.
- Adjudicating these findings **spends** them. They may be used to report
  precision and must not be used to tune the detector, which would consume the
  held-out corpora.
- This frame addresses one of the four requested measurements. False negatives
  need a different instrument: a reviewer reading skills without seeing
  Crucible's output, so that missed defects can be found. No such frame exists
  yet.
- `UNRESOLVED` is not a hidden rejection. A stratum's confirmed-of-decided
  ratio excludes unresolved items from the denominator, and the unresolved
  count is reported separately so it cannot be quietly dropped.

## Reproducing

```text
python docs/evidence/2026-10-23-adjudication-frame/build_frame.py <out-dir> 10 \
  <nimadorostkar-root>=nimadorostkar-claude-skills-collection \
  <terminalskills-root>=terminalskills-skills

python docs/evidence/2026-10-23-adjudication-frame/validate_adjudication.py \
  <out-dir>/frame.json <response-A.json> [<response-B.json>]
```

The builder refuses a corpus whose worktree is not clean.

# Blind false-negative review protocol

**Packet schema:** `false-negative-packet/v1`
**Commitment:** `sha256:b8156ca66b6e4dc2…` (see [`commitment.json`](commitment.json))
**State:** unlabeled; no review exists

## What is being measured

Whether Crucible misses methodological defects a careful human reader finds.
Crucible emits no finding at all for 569 of 1057 skills in one held-out corpus
and 34 of 138 in the other, so silence is its most common output and the least
examined.

This is a **discovery instrument**. It can establish that at least N missed
defects of M kinds exist in the reviewed skills. It cannot produce a
false-negative rate, a recall figure or an interval, and no result from it may
be reported as one.

## What the reviewer receives, and what they must not open

The reviewer receives [`reviewer-packet.json`](reviewer-packet.json): a corpus,
a path and a content digest per skill, plus each corpus's repository and
commit. It carries no finding, no finding count, no bucket and no audit
digest, and its order is produced by a different hash than the one used to
select, so position in the packet says nothing about which skills were silent.

The reviewer **must not open** `frame.PRIVATE.json`, any audit output, any
`docs/evidence/2026-10-23-adjudication-frame` file, or any Crucible report
over these corpora, until their own response is frozen. A reviewer who knows a
skill produced zero findings cannot produce an unbiased reading of it.

The frame itself is withheld rather than committed. `commitment.json` records
its digest, so the stratification and allocation are fixed and checkable
before any review exists and cannot be chosen afterwards to suit a result.

## Reporting defects

Report in your **own words**. You are deliberately not given Crucible's
finding-class list: naming the classes first would steer the review toward
defects Crucible already detects, which is the opposite of what this measures.

A methodological defect is an instruction that, if an agent followed it, would
make the agent work badly — unbounded work, an obligation with no way to check
it, a promise the instructions do not deliver, a step whose failure is
unhandled, a rule that contradicts another. These examples are illustrative,
not a checklist, and a defect that fits none of them is exactly the kind worth
reporting.

For each defect record: the description in your words, `line_start` and
`line_end` in the source file, a `quote` copied from the skill, and
`why_it_is_a_defect` — what following the instruction would cause.

**Reporting nothing for a skill is a valid and expected outcome.** Some skills
are clean. An empty `defects` list is a result, not a failure to engage.

Set `digest_verified` only after checking the file's SHA-256 against the
packet, and `read_completely` honestly. A skill you did not finish reading
cannot contribute its silence as evidence, and the validator excludes it from
every denominator rather than counting it as clean.

## Comparison procedure, frozen before any review

Fixed here so it cannot be adjusted once results are visible.

For each reviewed skill, each reported defect is compared against every
Crucible finding on that skill:

- **`CANDIDATE_MATCH`** — a finding whose `source_span.line` falls within
  `[line_start, line_end]` inclusive. Span overlap is deterministic and is
  **not** proof the two describe the same defect; one line can host two
  different problems. A candidate match requires a separately recorded
  adjudication to become `MATCHED` or `DIFFERENT_DEFECT`.
- **`UNMATCHED_REVIEWER_DEFECT`** — no finding overlaps it. This is a
  **candidate** false negative, and becomes a reported missed defect only
  after a recorded adjudication confirms the defect is real and that no
  Crucible finding covers it.
- **`UNMATCHED_FINDING`** — a Crucible finding no reported defect overlaps.
  This is a candidate false positive and cross-checks the precision frame,
  because the reviewer judged the same skill without seeing it.

No line tolerance is applied in either direction. Padding the span would raise
match counts and therefore lower apparent false negatives, which is the
direction of the result being measured, so the strict rule is the safe one.

A reviewer defect whose span does not overlap but which plainly corresponds to
an existing finding is recorded as a class-level match in the adjudication
step, with its reason, rather than by loosening this rule.

## Procedure

1. Clone each corpus at the commit in the packet. Verify every content digest
   before reading.
2. Review every item. Freeze your response before any discussion and before
   opening any Crucible output.
3. Run `validate_fn_response.py` against the packet. It checks structure,
   quotes and line ranges, and refuses a response that claims an authenticated
   identity no trust root supports.
4. Only then unseal the frame and run the comparison. Preserve the frozen
   response unchanged.
5. Report candidate matches, candidate false negatives and candidate false
   positives as candidates. Nothing becomes a confirmed missed defect without
   a recorded adjudication.

## Provenance and limits

Reviewer labels are self-reported. The repository has no trusted reviewer-key
policy and no signed-commit enforcement, so `authenticity_status` stays
`UNVERIFIED`; see the [reviewer trust assessment](../../red-team/2026-10-07-coverage-reviewer-trust-review.md).

Selection pools the two corpora, so the smaller one contributes 3 of the 24
items and **nothing is claimable per corpus**. The `6+` bucket draws 2 of 8
available skills, and `nimadorostkar` contributes none there because its
population in that bucket is 1.

Reviewing these skills spends them. They may be used to report missed defects
and must not be used to tune the detector, which would consume the held-out
corpus.

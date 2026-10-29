# Blind false-negative instrument

**Date:** 2026-10-23  **Branch:** `main`
**Commitment digest:** `sha256:b8156ca66b6e4dc2…`
**Frame digest (content withheld):** `sha256:a41ba9a960ce200e…`
**State:** `UNLABELED`. No skill has been reviewed.

## The gap this fills

The [adjudication frame](../2026-10-23-adjudication-frame/FINDINGS.md) asks
whether an emitted finding is real. It cannot see what Crucible never emitted.
On the held-out corpora, silence is Crucible's most common output:

| Corpus | Skills | Zero-finding skills |
|---|---|---|
| `TerminalSkills` | 1057 | 569 (54%) |
| `nimadorostkar` | 138 | 34 (25%) |

More than half of the larger held-out corpus produces no finding at all, and
nothing in the repository has ever tested whether that silence is correct.

## Design, and what each part is defending against

**Blindness.** A reviewer who knows a skill produced zero findings cannot read
it neutrally. [`reviewer-packet.json`](reviewer-packet.json) therefore carries
only `corpus_id`, `source_path`, `content_digest` and `item_index`, plus each
corpus's repository and commit. Verified: the strings `finding_count`,
`bucket`, `findings_total`, `audit_digest`, `stratification` and `allocation`
do not occur in it.

**Order leakage.** Selection ranks by `sha256("select|…")` and the packet is
ordered by `sha256("present|…")`, so position says nothing about bucket.
Verified: the bucket sequence in packet order is
`0 6+ 0 3-5 0 1-2 0 0 1-2 1-2 1-2 0 3-5 1-2 0 0 1-2 1-2 3-5 3-5 0 0 6+ 1-2`,
with 6 of the 10 silent items in the first half against 5 for a balanced
split.

**Choosing the stratification after seeing results.** The frame content is
withheld rather than committed; [`commitment.json`](commitment.json) records
its digest, so the buckets and allocation are fixed and checkable before any
review exists. The frame is published once the review is frozen.

**Anchoring to Crucible's ontology.** The reviewer is deliberately *not* given
the finding-class list. Handing over 30 class names would steer the review
toward the defects Crucible already detects, which biases the measurement in
the direction being measured. Reports are open-ended and in the reviewer's own
words; mapping a report onto a class is a separate, later, recorded step.

**Silence mistaken for cleanliness.** Each item carries `digest_verified` and
`read_completely`. An item not fully read and verified is excluded from every
denominator rather than counted as clean, and reporting defects against an
unverified file is refused.

## Stratification

Weighted toward the zero-finding bucket, since that is the condition under
test. 24 items from a population of 1195 skills:

| Bucket | Population | Selected |
|---|---|---|
| 0 findings | 603 | 10 |
| 1-2 | 506 | 8 |
| 3-5 | 78 | 4 |
| 6+ | 8 | 2 |

## Comparison procedure, frozen before any review

Fixed in [`PROTOCOL.md`](PROTOCOL.md) so it cannot be adjusted once results
exist. A reported defect is compared against every finding on the same skill:

- **`CANDIDATE_MATCH`** — a finding whose `source_span.line` lies within the
  reported `[line_start, line_end]`. Span overlap is *not* proof the two
  describe the same defect; one line can host two problems. Becoming `MATCHED`
  or `DIFFERENT_DEFECT` requires a recorded adjudication.
- **`UNMATCHED_REVIEWER_DEFECT`** — a candidate false negative.
- **`UNMATCHED_FINDING`** — a candidate false positive, which cross-checks the
  precision frame on skills a reviewer judged without seeing the findings.

No line tolerance in either direction. Padding spans would raise match counts
and therefore lower apparent false negatives, so the strict rule is the one
that cannot flatter the result.

## Validator negative controls

Thirteen adversarial inputs, all refused:

| Input | Error |
|---|---|
| defects reported against an unverified file | `defects reported against an unverified file` |
| `line_end` before `line_start` | `line_end precedes line_start` |
| defect missing the `quote` field | `expected exactly [...]` |
| `read_completely` as `"yes"` | `must be stated as true or false` |
| response not bound to the packet | `response is not bound to this packet digest` |
| `authenticity_status` raised to `VERIFIED` | `no reviewer trust root exists` |
| reviews reordered | `reviews do not match the packet items in order` |
| line number 0 | `must be a line number of 1 or more` |
| no `reviewer_label` | `reviewer_label is required` |
| frame allocation edited after sealing | `frame digest mismatch` |
| frame `audit_digest` edited | `frame digest mismatch` |
| a different corpus behind a sealed `corpus_id` | `audit digest differs from the sealed frame` |
| a corpus root omitted from the comparison | `no corpus root given for …` |

The last two matter most: they are the guards against comparing a frozen
review against a corpus or an auditor that changed after the frame was built.
Editing the frame's `audit_digest` is caught by the frame seal before the drift
check is reached, so the drift check was exercised by pointing a sealed
`corpus_id` at a different corpus instead.

A synthetic response exercised all four comparison routes: 4 candidate false
negatives in the zero-finding bucket, candidate matches and candidate false
positives in the buckets that have findings, and 22 of 24 items counted after
2 unread items were excluded.

## Limits

- **This is a discovery instrument, not an estimator.** 24 skills from 1195
  supports a lower bound of the form "at least N missed defects of M kinds
  exist in the reviewed skills". It supports no false-negative rate, no recall
  figure and no interval.
- **Nothing is claimable per corpus.** Selection pools the two corpora, so the
  smaller contributes 3 of 24 items and the `6+` bucket draws none from it.
- **Blindness rests on reviewer discipline, not on cryptography.** The packet
  names the 24 skills, so anyone holding the repository can run Crucible on
  them and learn the buckets. Withholding the frame raises the cost of
  accidental exposure; it does not prevent deliberate exposure.
- **A reviewer must be someone who has not seen the finding counts.** Whoever
  built this frame cannot serve as its reviewer, and neither can any session
  that has read the bucket distribution.
- **Reviewing spends these skills.** Results may be used to report missed
  defects and must not be used to tune the detector, which would consume the
  held-out corpus.
- **Severity is not collected.** The instrument records whether a defect was
  missed, not how much it matters. Ranking missed defects by consequence is a
  separate question.

## 2026-10-28 addendum: reproducibility depends on pinning Crucible's own commit

`frame.PRIVATE.json` was never saved after the original build; only
`commitment.json`'s digests were committed. Re-running `build_fn_frame.py`
today against the two pinned corpora, with Crucible at the current branch
HEAD, reproduced the same `packet_digest` but a **different** `commitment_digest`
and `frame_digest` — `audit_digest` differed for both corpora even though
`findings_total` stayed at 178 and 837. Seven `fix(audit)`/`fix(compiler)`
commits landed between this frame's build (`36db015`, 2026-10-23 20:56) and
now, changing audit content without changing the aggregate count. The claim
below that "all four outputs reproduce byte-identically across two runs" held
only for two runs made at the same Crucible commit; it does not hold against
a later HEAD, and nothing before this addendum recorded which Crucible commit
built the frame.

Checking out Crucible at `36db015` and rebuilding against the same two pinned
corpus commits reproduced `commitment_digest`, `frame_digest` and
`packet_digest` exactly. The resulting `frame.PRIVATE.json` is now saved
alongside this file (git-ignored, `*.PRIVATE.json`) so this reconstruction
does not need to be repeated.

**This session has now read that file's bucket distribution**, which the
"Limits" section above disqualifies from serving as the blind reviewer: "A
reviewer must be someone who has not seen the finding counts... neither can
any session that has read the bucket distribution." No bucket-level number
was relayed to the user in this conversation, but anyone choosing a reviewer
should not pick this session, and should be cautious about how much of this
conversation thread a prospective reviewer reads beforehand.

## Reproducing

```text
python docs/evidence/2026-10-23-false-negative-frame/build_fn_frame.py \
  <private-dir> <committed-dir> 24 \
  <nimadorostkar-root>=nimadorostkar-claude-skills-collection \
  <terminalskills-root>=terminalskills-skills

python docs/evidence/2026-10-23-false-negative-frame/validate_fn_response.py \
  <committed-dir>/reviewer-packet.json <response.json>

python docs/evidence/2026-10-23-false-negative-frame/validate_fn_response.py \
  <committed-dir>/reviewer-packet.json <response.json> \
  --compare <private-dir>/frame.PRIVATE.json \
  <nimadorostkar-root>=nimadorostkar-claude-skills-collection \
  <terminalskills-root>=terminalskills-skills
```

The builder refuses a corpus whose worktree is not clean. All four outputs
reproduce byte-identically across two runs.

# Blind rule/check relation review packet

**Packet schema:** `coverage-adjudication-packet/v1`

**Rubric:** `coverage-text/v1`

**State:** unlabeled; no gold links included

**Scope:** synthetic text-level review, not a representative corpus sample

## Purpose and limits

This packet prepares two independent reviewers to judge whether a check's
*text* specifies an observable check for a normative rule. It is designed to
exercise direct conditions, unrelated checks, partial rules, workflow text,
conditional scope, observable failure behavior, ambiguity, and multi-rule /
multi-check relations. Cases are synthetic and intentionally selected; results
can falsify a proposed rubric on these examples but cannot estimate corpus
accuracy or be generalized as a population metric.

The packet contains no expected outcomes, candidate scores, model suggestions,
or labels from the previous experiments. Packet authors did not write a hidden
answer key. A reviewer should assess every listed rule/check pair, not only
pairs that look related. Pair judgments in a multi-pair case are correlated;
do not treat the 19 pairs as 19 independent sampled observations.

## Review outcomes

Use exactly one outcome per pair:

- `COVERS`: the check text states an observable pass/fail criterion that
  addresses every applicable clause and precondition in the rule.
- `PARTIAL`: the check text specifies a criterion for some, but not all,
  relevant clauses or conditions. Name covered and uncovered clauses.
- `DOES_NOT_COVER`: available text shows the check tests a different property,
  or has no observable criterion for the rule.
- `UNRESOLVED`: context is insufficient or the relation cannot be decided
  consistently from this text.

These labels concern **textual specification only**. They do not mean that a
test was run, that an implementation passes, or that production behavior is
safe. A command or verification verb alone is not an oracle. A direct condition
without a verification verb can qualify when it states a falsifiable predicate
that matches the rule. Where a rule has multiple obligations, do not promote a
partial check to full coverage.

For each assessment, fill `covered_rule_clauses`, `oracle`, `evidence_quotes`,
and `rationale` in `response-template.json`. Quotes must be copied from the
packet, and the rationale should explain the match or mismatch at the
rule-predicate / check-oracle level. If `UNRESOLVED`, state the missing context.
Do not infer hidden implementation behavior.

## Independent review procedure

1. Give the same packet and a separate copy of the response template to each
   reviewer. Use neutral labels such as `reviewer-A` and `reviewer-B`; do not
   show prior labels, heuristic scores, model output, or the other reviewer's
   work.
2. Each reviewer completes and freezes their response independently before any
   discussion. Record the exact packet digest and rubric version in the
   response. Preserve the first submission unchanged.
3. Start with the `calibration` set. Compare disagreements only after both
   submissions are frozen. If the rubric changes, increment its version and
   treat calibration labels as consumed; do not relabel them as a fresh test.
4. Freeze the rubric and any candidate-link mechanism before opening the
   `heldout` labels. Keep each reviewer's heldout response sealed until that
   freeze. If the mechanism changes after labels are seen, the holdout is
   consumed and a new set is required.
5. Report per-reviewer labels, agreement and disagreement counts, outcomes by
   case, and all unresolved items. With this small, curated packet, do not
   report confidence intervals or corpus precision/recall.
6. Resolve a disagreement only through a separately recorded third review.
   Preserve both initial labels and the resolution. Until that process exists,
   disagreement remains `UNRESOLVED`.

## Provenance and authentication

The response template sets `authenticity_status` to `UNVERIFIED`. Reviewer
labels and key IDs are self-reported in this checkout. The local repository has
no trusted reviewer-key policy and no signed-commit enforcement; do not label
these submissions authenticated. The related [reviewer trust assessment](../../red-team/2026-10-07-coverage-reviewer-trust-review.md)
explains what a signature would and would not prove.

The calibration and heldout partitions were fixed before any labels were
collected. The heldout partition is not a random sample; it is a small adversarial
set for falsification only. A later corpus estimate requires a separately
sampled source corpus and fresh labels under a frozen rubric. Do not merge this
packet into the earlier six-case mechanism experiment or use its old thresholds
as ground truth.

## Files

- `packet.json` — fresh synthetic cases and every rule/check pair, without
  expected labels.
- `response-template.json` — blank response rows for all 19 pair judgments.
- `validate_packet.py` — structural consistency check and packet digest output.

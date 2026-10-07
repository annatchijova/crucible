# ADR-0024 — Require rule-to-check evidence for coverage claims

**Date:** 2026-10-07  **Status:** Proposed; experiment required before
implementation  **Reversibility:** one-way-ish if persisted IR or finding
contracts change; low if limited to a new audit finding.

## Forces at the time

- L1 currently extracts `rules`, `checks`, and `procedural_steps` independently.
- L2 `REQUIREMENT_WITHOUT_CHECK` skips a skill whenever its `checks` list is
  nonempty; checks are not linked to individual rules.
- A workflow-shaped item under `Live Odds Check` reproduced a false negative.
- A source-overlap filter would add ten candidates on the previously consumed
  427-file slice, including plausible verification operations.
- A four-fixture route pilot found `oracle_kind` cannot distinguish a useful
  verification operation from a workflow command.
- A new local fixture showed that a real signature check unrelated to an
  idempotency rule also suppresses the missing-coverage candidate.
- A second fixture showed that one check relevant to one of two normative rules
  suppresses the candidate for both; shared-token overlap cannot distinguish
  the two rules because they share the noun `request`.
- The relevant pinned source corpus is not present in this checkout; broad
  impact replay is unavailable offline.

## Decision under consideration

Do not make check/workflow classification the sole basis for requirement
coverage. Prototype distinct relation states: no check candidate; link unknown;
link declared or proposed with source provenance; and link adjudicated with
scope and evidence. A declaration or proposal alone is not verified coverage.

Keep the L1 extractor deterministic and structural during the prototype. Compare
explicit annotations, deterministic references, and separate confirmation
artifacts as possible sources of link evidence. This proposal does not yet
choose among them and authorizes no persisted schema change.

The current preference is to keep source declarations, deterministic candidates,
model observations, and human adjudications as distinct provenance states. An
author declaration or model proposal alone is not proof that a check adequately
verifies a rule. The model must not change the sealed L2 verdict; any returned
IDs must be validated against the input artifact. Source review of the existing
L2.5-to-L15 path shows that a separate evidence artifact can feed a downstream
recommendation while leaving L2 immutable. Therefore, “never affect any
recommendation” is not the required boundary; the consumer, authority, and
claim must be explicit. A coverage map that changes an L2 finding is rejected.
A separately versioned L15 input remains a candidate design, not an accepted
decision, and must bind both source digests, validate IDs/conflicts, authenticate
adjudication provenance, and appear in the composite report's digest chain.
See the mechanism/consumer comparison and the [authority boundary red-team
review](../red-team/2026-10-07-coverage-map-authority-review.md).

## Alternatives considered

- **Exclude check-shaped items that overlap `procedural_steps`.** Rejected as a
  general fix because the impact replay admitted plausible checks and the
  run-and-print workflow does not overlap the procedural extractor. Best point:
  the predicate is cheap and fixes the original numbered workflow fixture.
- **Use `oracle_kind` as the coverage gate.** Rejected because it describes
  lexical form, not semantics or rule linkage: the valid exact-status criterion
  is `unknown`, while the run-and-print workflow is `command`. Best point: the
  existing field is deterministic and already tested.
- **Use a small lexical acceptance-predicate classifier.** Deferred because its
  four-for-four fit is post-hoc on curated fixtures and offers no independent
  estimate. Best point: it may be a useful high-precision signal if paired with
  an explicit abstain state.
- **Keep the current skill-level nonempty check gate.** Rejected because a
  genuine but unrelated check suppresses a requirement finding. Best point: it
  avoids candidate volume and remains a cheap coarse signal.
- **Map checks to rules by shared tokens.** Rejected for the partial-coverage
  fixture because both rules share a generic noun with the check. Best point:
  deterministic lexical links are cheap, explainable, and may still be useful
  as candidate evidence when they are not treated as proof.
- **Treat an author annotation as verified coverage.** Rejected as an
  unqualified claim: the annotation is a source declaration, not evidence that
  the check's oracle is adequate. Best point: a stable author-owned ID is
  precise, deterministic, and supports imported or reviewed documents that
  voluntarily adopt the convention.
- **Let L2.5 decide the L2 coverage verdict.** Rejected by the existing
  deterministic-core contract. Best point: the model can inspect paraphrases
  and whole-skill context that deterministic links miss; retain it as a separate
  observation or a review aid, never as an automatic mutation of L2.

## Assumption

Coverage is a relation between a normative rule and an observable check, not a
property of a skill as a whole. If Crucible intentionally defines coverage at
skill level, this proposal is wrong and the finding name/evidence must be
narrowed instead.

## Consequences

Accepted for the experiment: missing links remain explicitly unknown; no
heuristic will be described as semantic ground truth. Deferred: the finding
taxonomy, annotation syntax, IR schema version, consumer migration, corpus
impact, and whether link proposals can be consumed by L15.

## Revisit trigger

The first mechanism comparison and a source-confirmed authority-boundary review
are recorded in the linked experiment and its red-team companion. The matrix
uses six synthetic fixtures with five labeled cases and one explicit abstention.
It confirms the predicted threshold trade-off but is not independent
validation: thresholds were informed by an earlier consumed fixture, labels
were authored for this exercise, and no model was run. Do not treat this
trigger as satisfied. Accept, revise, or reject after an independently
adjudicated fixture set tests positive, negative, ambiguous, partial, and
misdeclared relations, including explicit abstention behavior. Any
implementation proposal must include consumer inventory, artifact
compatibility treatment, corpus impact evidence, and a validated human/model
output contract before changing the auditor.

## Evidence

See [the local hypothesis experiment](../evidence/2026-10-07-check-coverage-hypothesis-experiment.md)
and the prior [check-heading adjudication](../red-team/2026-10-07-check-heading-adjudication.md),
plus the [coverage-map authority review](../red-team/2026-10-07-coverage-map-authority-review.md).

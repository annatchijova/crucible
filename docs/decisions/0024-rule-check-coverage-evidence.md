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
coverage. Prototype a three-state audit contract: no check candidate, check
candidate with rule linkage unknown, and rule-check link evidenced. Only the
third state may support a claim that a specific rule has a verification path.

Keep the L1 extractor deterministic and structural during the prototype. Compare
explicit annotations, deterministic references, and separate confirmation
artifacts as possible sources of link evidence. This proposal does not yet
choose among them and authorizes no persisted schema change.

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

## Assumption

Coverage is a relation between a normative rule and an observable check, not a
property of a skill as a whole. If Crucible intentionally defines coverage at
skill level, this proposal is wrong and the finding name/evidence must be
narrowed instead.

## Consequences

Accepted for the experiment: missing links remain explicitly unknown; no
heuristic will be described as semantic ground truth. Deferred: the finding
taxonomy, annotation syntax, IR schema version, consumer migration, corpus
impact, and whether link proposals can be confirmed in L2.5.

## Revisit trigger

Accept, revise, or reject this proposal after the adversarial fixture matrix is
run and the candidate link mechanisms are compared for positive, negative, and
partial coverage. Any implementation proposal must include consumer inventory,
artifact compatibility treatment, and corpus impact evidence before changing
the auditor.

## Evidence

See [the local hypothesis experiment](../evidence/2026-10-07-check-coverage-hypothesis-experiment.md)
and the prior [check-heading adjudication](../red-team/2026-10-07-check-heading-adjudication.md).

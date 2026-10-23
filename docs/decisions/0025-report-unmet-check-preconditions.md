# ADR-0025 — Report an unmet check precondition instead of an empty result

**Date:** 2026-10-23  **Status:** Accepted; implemented in this change
**Reversibility:** low to reverse the schema (two version bumps already
published in-repo); the computation itself is additive and removable.

## Forces at the time

- `AUDIT_LIMITATIONS` was an empty list and `GRAPH_LIMITATIONS` a static
  module constant. Neither artifact had any mechanism to report a
  corpus-dependent unmet precondition, so an empty result was always reported
  the same way regardless of why it was empty.
- On the pinned 818-skill external corpus the composition graph produced 0
  edges while reporting the same three limitations it reports for a corpus
  where composition resolved
  ([evidence](../evidence/2026-10-23-composition-silent-on-external-corpus/FINDINGS.md)).
- Rule `subject` extraction yielded 1 of 818 skills, so
  `_check_normative_conflict` and `_check_conditional_contradiction` compared
  zero pairs and emitted nothing
  ([evidence](../evidence/2026-10-23-rule-extraction-yield/FINDINGS.md)).
- `_check_orphan_skills` already contained a deliberate `has_any_edge` guard
  with a documented reason, and returned `[]` silently. The decision to
  abstain existed; only its visibility did not.
- `human_output.py` rendered the static limitation list as
  "N check(s) abstained", telling every reader of every corpus that three
  checks abstained. The word was already in use and already wrong.
- `CLAUDE.md` section 5.3 requires three states rather than two, and requires
  warning at the boundary where degradation enters.

## Decision

Separate two things that were conflated under one word.

**`limitations`** keeps its existing meaning: permanent design scope,
identical for every corpus. It is not a per-run signal and is now rendered as
"documented design limitation(s)".

**`preconditions`** is new, corpus-derived and sealed. For each check class
whose input was verified against that check's own code, it reports the input
required, the whole-number count observed, and an outcome of `EXERCISED` or
`ABSTAINED`, with a reason only when abstained. It carries the corpus input
counts it was computed from and a fixed limitation sentence stating that an
abstained check finding nothing is not evidence the corpus is clean.

Eight check classes are covered, each mapped to the input its code reads:
`BROKEN_REFERENCE`, `COMPOSITION_CYCLE`, `ORPHAN_SKILL` and
`SELF_COMPOSITION` to `declared_relations`; `NORMATIVE_CONFLICT` and
`CONDITIONAL_CONTRADICTION` to `comparable_rule_pairs_by_subject`;
`SEMANTIC_REDUNDANCY` to `comparable_skill_pairs`;
`REQUIREMENT_WITHOUT_CHECK` to `rules`.

The graph gains the same treatment for edge construction, reporting declared
section relations and description trigger matches, and abstaining only when
both are zero.

## Consequences accepted

- `AUDIT_VERSION` moves to `crucible-audit/v2` and `GRAPH_VERSION` to
  `crucible-graph/v2`. Every audit and graph digest changes. Three existing
  version assertions failed on this change and were updated; no test pinned a
  literal digest, so nothing else moved.
- Preconditions are inside the sealed payload. They are structural integer
  facts about the compiled IR and are decision-relevant, unlike
  `cost-record/v1`, which is explicitly non-deterministic and sealed
  separately with no authority.
- The audit pays one extra `_skill_token_set` pass. Measured on the 818-skill
  corpus: 1668 ms to 1713 ms, 2.7%. The pass was kept separate rather than
  threaded out of `_check_semantic_redundancy` so that check's behaviour is
  untouched.
- `human_output` renders a legacy artifact without `preconditions` without
  claiming any abstention.

## What this does not do

- It does not improve detection. Every abstention this surfaces was already
  happening; the change is that the artifact now says so. Six of the eight
  covered checks abstain on **both** real corpora, including the author's own,
  which means they have never fired outside fixtures.
- It does not cover every check, only those whose consumed input was verified
  in code. A check not listed in `_CHECK_PRECONDITIONS` reports nothing, and
  absence from that list is not a claim that the check has no precondition.
- It does not make an `EXERCISED` outcome evidence of correctness. It means
  the input existed, not that the check is accurate on it.
- It does not address the underlying rule-extraction yield. Widening the
  modal vocabulary would tune against an already-consumed corpus and is
  deferred until a held-out corpus is sealed.

## Rejected alternatives

- **Populate `AUDIT_LIMITATIONS` per corpus.** Rejected: it would overload one
  field with permanent design scope and per-run abstention, which is the
  conflation that produced the misleading human output in the first place.
- **Emit an `ABSTAINED` finding per check.** Rejected: findings are per-skill
  source-addressable records with an epistemic status, and an abstention is a
  corpus-level fact with no source span. It would also inflate finding counts.
- **Have each check return its own precondition outcome.** Better
  architecture and a larger change across roughly thirty checks. Deferred;
  the current mapping is a verified table, and ADR revision is the path if a
  check's consumed input changes.
- **Leave it to documentation.** Rejected: the artifact is what downstream
  consumers, the viewer and the report read. A limitation only present in prose
  does not reach them.

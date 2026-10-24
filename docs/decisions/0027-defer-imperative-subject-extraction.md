# ADR-0027 — Do not derive a rule subject from imperative prose yet

**Date:** 2026-10-23  **Status:** Accepted; nothing implemented by this
decision beyond making the existing limitation legible
**Reversibility:** high. No schema, no persisted field and no check behaviour
changes, so a later implementation starts from the current state.

## Forces at the time

- Across five real corpora totalling 2806 skills, rule `subject` extraction
  yielded 27 occurrences, 22 of them in the author's own corpus
  ([five-corpus replication](../evidence/2026-10-23-heldout-replication/FINDINGS.md)).
- `NORMATIVE_CONFLICT` and `CONDITIONAL_CONTRADICTION` both group or filter by
  `subject`, so both compared **zero** pairs on every one of the five corpora.
  They are two of the six precondition-dependent checks that have never fired
  outside fixtures.
- `CONDITIONAL_CONTRADICTION` is the check closest to the typed-composition
  boundary this project proposes, which makes its silence the most costly and
  its false positives the most damaging.
- The cause is not a parsing failure. `compiler.py:_extract_rules` has three
  routes and only the RFC-2119 modal route assigns a subject; the
  negative-starter (`Never`, `Always`) and imperative routes record `""` by
  construction, as that function's docstring already states ("no NLP object
  extraction"). Measured: 219 of mukul975's 221 rules and 302 of vantaflow's
  302 come from those routes, so only 2 and 0 rules respectively ever reached
  subject extraction at all.
- For an imperative rule the constrained entity is the **object** of the verb
  ("Never commit *secrets* to the repository"), not a noun phrase before a
  modal. Recovering it is object extraction, which this project deliberately
  excluded.
- Six days remain before a submission whose build currently passes.

## Decision

Keep `subject` as an RFC-2119-modal-route field only. Do not derive a subject
from imperative or negative-starter prose now.

The limitation is made legible rather than left to be inferred: the abstention
reason for both checks now names the actual cause and points the reader at
`rules_with_subject`, so a low count is not misread as subjects extracted and
unmatched. The published claims were bounded accordingly on the same day in
`TECHNICAL.md` section 6 and `COMPETITIVE_BOUNDARY.md`.

## Why not the conservative lexical prototype

It was the obvious candidate and is rejected for now on a specific asymmetry,
not on effort.

`subject` is consumed by **pairwise** checks. A wrong subject does not merely
miss a conflict; it manufactures one, by pairing two unrelated rules that the
heuristic happened to normalize to the same string. Generic nouns make this
likely: the earlier shared-token work already recorded two rules colliding on
the noun `request` ([ADR-0024](0024-rule-check-coverage-evidence.md)). A false
`NORMATIVE_CONFLICT` lands on the check closest to the published
differentiator, which is the worst place in the system to put a false
positive.

Against that, the current cost is silence that is now **reported as
silence**. `ABSTAINED` with a cause is a WARN, not a false PASS, which is the
posture `CLAUDE.md` section 5.3 asks for. Trading a reported abstention for an
unquantified false-positive rate on the project's most load-bearing check is
the wrong direction, and six days is not enough to quantify it.

## Rejected alternatives

- **Conservative lexical object extraction.** Deferred, not rejected on
  principle; see above. Best point: it is deterministic, cheap and explainable,
  and would unlock two checks on the most common rule style in real corpora.
- **Change what the pairwise checks compare.** Same false-positive exposure,
  more invasive in the auditor, and it would move the heuristic from the IR
  into the decision path where it is harder to inspect. Best point: it leaves
  the persisted IR untouched.
- **Let a model extract the subject.** Rejected by the deterministic-core
  contract: `subject` feeds a sealed L2 verdict, and `CLAUDE.md` section 5.1
  keeps the model out of the decision path. A model could propose a subject
  only as a separate observation artifact that never mutates L2, which is the
  provenance-state design [ADR-0024](0024-rule-check-coverage-evidence.md)
  already sketches.
- **Delete the two checks.** Rejected: the checks are correct for the rule
  style they were built for, they fire on fixtures, and removing them would
  destroy a specification rather than record that its precondition is rarely
  met.

## Consequences accepted

- `NORMATIVE_CONFLICT` and `CONDITIONAL_CONTRADICTION` stay structurally inert
  on any corpus that does not write obligations as subject-before-modal. On
  the evidence to date that is every corpus measured except the author's own,
  and even there no two rules shared a subject.
- The typed-composition boundary remains a specification the implementation
  does not exercise on third-party corpora. That is now stated where the
  claim is published rather than only in an evidence record.
- Anyone reading a clean audit of a real corpus must read `preconditions` to
  know these checks did not run. The artifact says so; a reader who ignores it
  will overread the result.

## Revisit trigger

Falsifiable, and ordered so that a held-out corpus is not spent on a
heuristic that fails early:

1. Implement candidate object extraction behind a flag, emitting it as a
   **separate provenance state** (`derived`, distinct from a modal-route
   subject), never silently as `subject`.
2. Measure on the two `TUNING_CONSUMED` corpora only: how many new
   `NORMATIVE_CONFLICT` and `CONDITIONAL_CONTRADICTION` candidate pairs
   appear, and adjudicate a stratified sample of them.
3. Proceed only if the adjudicated sample shows the new pairs are
   predominantly real, with the denominator and the sample reported. A
   majority of spurious pairs closes this permanently rather than inviting a
   threshold hunt.
4. Only after that, and with the mechanism frozen, measure once on a held-out
   corpus. Iterating against held-out results consumes the corpus.

Do not treat an improved subject count as the result. The result is whether
the pairs the checks newly compare are real.

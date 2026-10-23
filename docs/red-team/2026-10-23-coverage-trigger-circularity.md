# ADR-0024's revisit trigger cannot be satisfied by its own packet

**Date:** 2026-10-23  **Base:** `094a087`  **Method:** audit of the prepared
packet against the exit criterion it was built to satisfy  **Status:**
blocking defect in the exit criterion, not in the packet

## Why this review exists

The 2026-10-07 block ended with a blind review packet "ready for independent
human review" and an ADR whose status is "Proposed; experiment required before
implementation". The obvious next step is to spend two independent reviewers
on the packet. Before doing that, the packet was checked against the criterion
it is supposed to discharge, as `CLAUDE.md` section 4.1 requires for any
finding one did not derive from the live artifact oneself.

## Firstness — what the artifacts say

ADR-0024's revisit trigger:

> Accept, revise, or reject after an independently adjudicated fixture set
> tests positive, negative, ambiguous, partial, **misdeclared, stale, and
> conflicting** relations, including explicit abstention behavior.

The packet's own structure, enumerated from `packet.json`:

- case fields: `case_id`, `source_text`, `rules`, `checks`, `pairs`
- rule fields: `id`, `text`
- check fields: `id`, `section`, `text`
- pair fields: `pair_id`, `rule_id`, `check_id`

Substring counts over the whole packet: `declar` 0, `link` 0, `covers` 0,
`stale` 0, `conflict` 0, `misdeclar` 0, `verified_by` 0, `oracle` 0.

`PROTOCOL.md` scopes the rubric itself: "These labels concern **textual
specification only**."

Case shapes: 15 of 16 cases are one rule by one check. One case, `case-6ae1`,
contributes 4 of the 19 pairs.

Integrity reproduces: the validator emits identical output across two runs,
16 cases, 19 pairs (9 calibration, 10 heldout), `answer_labels_present:
false`, `template_matches_pairs: true`, packet digest
`sha256:82d8e9758966eab1…`.

## Secondness — the deviation

Three of the seven relation kinds the trigger names are **not testable by this
packet, and not because no reviewer has run it**:

| Relation kind | Testable from this packet | Why |
|---|---|---|
| positive | yes | e.g. `case-2f8a`, a checksum rule with a checksum equality check |
| negative | yes | e.g. `case-61bd`, a line-endings rule with a signature check |
| ambiguous | yes | the rubric carries `UNRESOLVED` |
| partial | yes | e.g. `case-a42e`, two obligations with a check for one |
| explicit abstention | yes | `UNRESOLVED` is a required outcome |
| **misdeclared** | **no** | requires a declared link that is wrong; the packet contains no declarations |
| **stale** | **no** | requires a declared link whose target changed; no declarations and no versioning |
| **conflicting** | **no** | requires two declarations or sources to disagree; no declarations |

A reviewer given this packet judges whether a check's *text* specifies an
observable criterion for a rule's *text*. That is a real and useful question,
and it is not the declaration-state question. No labelling effort on these 19
pairs can produce evidence about a misdeclared, stale or conflicting link,
because no such object is present to misdeclare, stale, or conflict.

## Thirdness — the general rule, and the circularity

The three missing kinds are states of the relation *layer* ADR-0024 proposes:
"no check candidate; link unknown; link declared or proposed with source
provenance; and link adjudicated with scope and evidence". Authoring a
misdeclared or stale fixture requires first fixing how a link is declared.

ADR-0024 explicitly defers exactly that:

> Deferred: the finding taxonomy, **annotation syntax**, IR schema version,
> consumer migration, corpus impact, and whether link proposals can be
> consumed by L15.

So the ADR defers the annotation syntax while requiring, as its exit
criterion, adjudicated fixtures for three relation states that cannot exist
without an annotation syntax. The rule:

> An exit criterion that depends on a design decision the same document
> defers cannot be discharged by any amount of review. The dependency, not
> the reviewer supply, is the blocker.

## Refutation attempted

Two benign hypotheses were built and tested.

1. *"Misdeclared" means a check whose text misdescribes what it verifies,
   needing no annotation.* Rejected against the document. ADR-0024's
   alternatives list "Treat an author annotation as verified coverage" and the
   decision enumerates `link declared or proposed with source provenance`, so
   declaration is the subject of these states. A check whose text does not
   match the rule is already the `DOES_NOT_COVER` outcome the packet tests,
   which would make "misdeclared" a duplicate of "negative" rather than a
   seventh kind.
2. *The packet is a first instalment and the trigger is known to need more.*
   Partly right and not sufficient. The red-team disposition of 2026-10-07
   says the packet "is ready for independent human review as a curated
   falsification set only", which correctly narrows the packet. Neither that
   review nor the ADR says the trigger needs a second artifact, and the ADR
   lists the packet under Evidence for the trigger. The gap is unrecorded,
   which is what makes it actionable now.

## Consequence

The 2026-10-07 work is sound within its own scope and the packet's integrity
reproduces. The defect is in the exit criterion. Two corrections follow:

- **Split the trigger.** The text-level rubric question can be discharged by
  independent human review of this packet. The declaration-state question
  needs its own artifact and cannot be opened before the annotation syntax is
  chosen. One gate cannot cover both.
- **Do not spend the two reviewers against the wrong claim.** Reviewing this
  packet is still worth doing, and what it buys must be stated beforehand:
  evidence about the text rubric on 19 curated synthetic pairs, not a
  discharge of ADR-0024.

One further limit worth recording before review: multi-rule / multi-check
relations rest on a single case. `case-6ae1` supplies 4 of 19 pairs, so
agreement or disagreement there is one observation, not four.

## What this review does not establish

It does not assess any rule/check relation, does not label any pair, and does
not evaluate the rubric's quality. It compares a prepared artifact against a
written exit criterion. No packet file, rubric version or partition was
modified; the packet remains `UNLABELED` at digest
`sha256:82d8e9758966eab1…`.

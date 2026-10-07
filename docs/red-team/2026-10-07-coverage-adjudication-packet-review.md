# Blind coverage-review packet — red-team and integrity review

**Date:** 2026-10-07  **Base:** `db63a97`  **Method:** packet structure review,
answer-leakage negative control, and digest-binding negative control  **Status:**
packet prepared; no reviewer responses or semantic labels exist.

## Scope and prediction

This checks whether the review packet can be handed to two reviewers without
embedding an answer key, omitting a rule/check pair, or silently changing the
reviewed material. It does not establish the semantic correctness of any
relation. Cases are new synthetic text, not an independently sampled source
corpus.

Pre-run predictions:

1. The packet contains 16 unique cases across calibration and heldout, with all
   rule/check Cartesian pairs represented exactly once (19 pairs total).
2. The response template has one blank assessment for each pair and binds the
   packet's canonical digest.
3. The packet checker rejects a gold-label field and rejects a mismatched
   response-template digest.

## Artifacts and result

- [`PROTOCOL.md`](../evidence/coverage-adjudication-packet-2026-10-07/PROTOCOL.md)
  defines text-level outcomes, independent review steps, heldout handling, and
  provenance limits.
- [`packet.json`](../evidence/coverage-adjudication-packet-2026-10-07/packet.json)
  contains nine calibration and seven heldout cases. The heldout portion has
  ten relation pairs, including the four-way matrix case.
- [`response-template.json`](../evidence/coverage-adjudication-packet-2026-10-07/response-template.json)
  contains 19 blank rows, is bound to packet digest
  `sha256:82d8e9758966eab173a83909bd81972c3a79a70b96a11d4261e7ec5e05ccf367`,
  and declares reviewer authenticity `UNVERIFIED`.
- [`validate_packet.py`](../evidence/coverage-adjudication-packet-2026-10-07/validate_packet.py)
  checks schema/rubric version, unique case IDs, complete pair products,
  source-text inclusion, absence of answer/prediction keys, response-template
  alignment, and packet digest.

The validator observed 16 cases, 19 pairs (9 calibration; 10 heldout), no
answer labels, and an aligned template. Two runs emitted identical output.
Adding a temporary `gold_label` field made it exit 1 with
`packet includes an answer or prediction field`. Restoring the packet returned
it to pass. Replacing the response template's packet digest with a placeholder
also made it exit 1 with `response template is not bound to this packet digest`;
restoration returned it to pass. The two temporary mutations were removed.

During packet construction, the checker caught two context mismatches: one
check combined text from separate workflow lines, and one decomposed a compound
rule into clauses not present verbatim in the excerpt. Those entries were
rewritten so the reviewer now sees the source wording and the extracted item
wording distinctly. The final packet passed the source-text inclusion check.

## Red-team interpretation

This establishes only packet integrity and coverage of the intended review
matrix. It does not establish reviewer independence, reviewer identity,
reviewer expertise, or semantic correctness. Case authors know the challenge
patterns, and the set is adversarially selected; even perfect agreement is not
a corpus accuracy estimate. The 19 pair decisions are clustered within 16
cases, and one case contributes four correlated pairs.

The calibration responses may be used to identify rubric ambiguity. If the
rubric changes, increment `rubric_version` and discard calibration as a test
set. Keep heldout responses sealed until the rubric and any proposed mechanism
are frozen. A reviewer response returned to this repository remains
`UNVERIFIED` until a trusted key-to-reviewer policy exists; a self-reported
name or key does not change that status.

## Disposition

The packet is ready for independent human review as a **curated falsification
set only**. No L1/L2/confirmation/recommendation behavior or persisted schema
changed. Do not score lexical or model mechanisms against these cases until the
two initial assessments are frozen; do not describe any resulting labels as
ground truth beyond this rubric and these synthetic examples.

Reproduce packet validation with:

```text
.venv/bin/python docs/evidence/coverage-adjudication-packet-2026-10-07/validate_packet.py
```

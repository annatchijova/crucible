# Reviewer response validator — negative controls

**Date:** 2026-10-23  **Base:** `8813d54`  **Method:** ten adversarial
submissions against a new response validator, plus the calibration-first
workflow  **Status:** Gate A is now executable; no label exists

## Why this exists

`validate_packet.py` checks that the packet can be handed out. Nothing checked
what comes back. A reviewer could have returned an outcome outside the rubric,
a paraphrased quote, a `PARTIAL` with no clauses named, a response bound to a
different packet, or a response claiming an authenticated identity, and the
repository would have accepted all five as labels.

Gate A of [ADR-0024](../decisions/0024-rule-check-coverage-evidence.md) cannot
be discharged by labels that were never structurally checked, so this had to
exist before reviewers start, not after.

## What the validator enforces

Per `PROTOCOL.md`: the response is bound to the packet digest and rubric
version; `reviewer_label` is present; `authenticity_status` stays `UNVERIFIED`
because no reviewer trust root exists; assessment rows match the packet's pair
order exactly; every outcome is one of `COVERS`, `PARTIAL`, `DOES_NOT_COVER`,
`UNRESOLVED`; every judgement carries a rationale and at least one quote; each
quote is a substring of that case's `source_text`, since the protocol requires
quotes to be copied rather than paraphrased; `PARTIAL` names covered clauses;
`COVERS` and `PARTIAL` name an oracle; `DOES_NOT_COVER` lists none.

It also computes agreement counts and lists every disagreement with the
disposition `UNRESOLVED pending a separately recorded third review`, matching
protocol step 6.

It deliberately computes no accuracy, no kappa and no interval. There is no
answer key, the 19 pairs are correlated within 16 cases, and protocol step 5
forbids corpus estimates from this set. The report carries that limitation as
a fixed string.

## Negative controls

Each row is a deliberately malformed submission built from a synthetic
response. The synthetic responses were kept outside the repository so they can
never be mistaken for labels.

| Adversarial submission | Result |
|---|---|
| outcome `MOSTLY`, outside the rubric | exit 1, `outcome 'MOSTLY' is not in the rubric` |
| quote paraphrased rather than copied | exit 1, `quote is not copied from the packet` |
| `PARTIAL` with no covered clauses | exit 1, `PARTIAL must name the covered clauses` |
| `authenticity_status` raised to `VERIFIED` | exit 1, `no reviewer trust root exists; status must stay UNVERIFIED` |
| `packet_digest` rebound to another value | exit 1, `response is not bound to this packet digest` |
| judgement with a whitespace rationale | exit 1, `a rationale is required for every judgement` |
| the same `reviewer_label` submitted twice | exit 1, `both responses carry the same reviewer_label` |
| `reviewer_label` null | exit 1, `reviewer_label is required` |
| one pair row deleted | exit 1, `assessments do not match the packet pair order` |
| two well-formed responses | exit 0, 19 pairs compared, 19 disagreements listed |

A tenth check was attempted and is recorded as a boundary rather than a
failure: the blank `response-template.json` is rejected, because it has no
`reviewer_label`. That is correct. The template is not a submission; it is
validated by `validate_packet.py`, and submissions by this script.

## Calibration-first workflow

Protocol step 3 starts with calibration and step 4 keeps heldout sealed.
Verified with two synthetic responses whose heldout rows were left null: each
reported `answered 9`, `blank 10`, `phases_complete ["calibration"]`, the
comparison covered 9 pairs, and every disagreement was in the calibration
phase. The heldout partition is reportable as untouched rather than assumed.

## State of Gate A

- Packet integrity reproduces: digest
  `sha256:82d8e9758966eab1…`, 16 cases, 19 pairs,
  `answer_labels_present: false`. Unchanged by this work.
- `response-reviewer-A.json` and `response-reviewer-B.json` are committed as
  separate blank forms, as protocol step 1 requires, so neither reviewer edits
  a shared file. Both validate with `answered 0`, `blank 19`.
- Remaining blocker: two independent human assessments. That is reviewer
  supply, not missing machinery.

## What this does not establish

No pair was judged and no rubric quality was assessed. Every outcome in the
controls above is a synthetic constant chosen to exercise a check, never a
judgement about a rule/check relation. Agreement counts from this validator
are not evidence that either reviewer is correct, and Gate A discharges only
the text-level rubric question, not ADR-0024.

Reproduce with:

```text
.venv/bin/python docs/evidence/coverage-adjudication-packet-2026-10-07/validate_packet.py
PYTHONPATH=src .venv/bin/python docs/evidence/coverage-adjudication-packet-2026-10-07/validate_response.py <response-A.json> <response-B.json>
```

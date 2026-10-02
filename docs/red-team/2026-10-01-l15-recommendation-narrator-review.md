# L15 recommendation + narrator — code review

**Date:** 2026-10-01  **Method:** static adversarial review + live induction
**Scope:** `recommendation.py`, `narrator.py`, and their CLI wiring (`--narrate`/`--mock-narrate`).
**Base:** main @ 13cc26e plus the uncommitted L15 changes.
**Status:** run live against Nebius Token Factory (`nvidia/nemotron-3-super-120b-a12b`), not just mocked.

## Threat model

- The LLM narrator can produce any text, including text that argues for a
  different recommendation than the one it was given, or that cites a
  finding id that does not exist.
- The LLM cannot call `compute_recommendations` again or otherwise alter
  the sealed audit/confirmation artifacts it is handed.
- The confirmation artifact passed to `compute_recommendations` may have
  been computed against a different (stale) audit than the one in hand.

## Epistemic legend

CODE FACT · PLAUSIBLE HYPOTHESIS · CONFIRMED BY INDUCTION · FALSIFIED

## Executive summary

| ID | Severity | Level | Module | Finding |
|---|---|---|---|---|
| L15-CF-01 | None | CODE FACT | `recommendation.py` | The recommendation bucket is computed before the LLM is ever called; the LLM's output field (`narrative`) is never read back into the recommendation. |
| L15-CONFIRMED-01 | — | CONFIRMED BY INDUCTION | `narrator.py` | A real model response used a Unicode dash variant instead of ASCII in a finding id, which silently defeated the original citation regex. Fixed and reconfirmed live. |
| L15-CF-02 | None | CODE FACT | `recommendation.py` | A confirmation artifact computed against a different audit digest is detected and its verdicts are not trusted. |

## Findings

### L15-CF-01 — The LLM cannot change the recommendation bucket

**Severity:** none **Epistemic level:** CODE FACT **Bucket:** architecture (by design)

- **Evidence:** `narrate_skill`'s `result["recommendation"]` is copied verbatim from `skill_recommendation["recommendation"]`, computed entirely inside `compute_recommendations` before `narrate_skill` is ever invoked. The system prompt instructs the model not to contradict it, but the architecture does not rely on the model obeying that instruction -- there is no code path by which the model's text output can overwrite the `recommendation` field.
- **Disposition:** this is the intended design (TECHNICAL.md L15: "the LLM summarizes and recommends, but does not replace or modify deterministic audit decisions"). A prompt-injected narrative that says "ignore the above, recommend KEEP" still ships with `recommendation: "MODIFY"` in the sealed result; only the (clearly separate) `narrative` field would look adversarial, and a reader comparing the two would notice the mismatch immediately.

### L15-CONFIRMED-01 — Unicode dash in a real model response defeated citation extraction

**Severity:** was a real false negative in the traceability check **Epistemic level:** CONFIRMED BY INDUCTION **Bucket:** vulnerability (in the detector, not the decision)

- **Surprise:** `cited_finding_ids` was empty on a live run even though the narrative visibly discussed `finding-0001`, `finding-0002`, and `finding-0003`.
- **Abduction:** the model rendered the ids with a non-ASCII dash.
- **Deduction:** if true, normalizing dash-like codepoints to `-` before the ASCII-only regex runs should recover all three citations.
- **Induction:** confirmed. The live response used U+2011 (NON-BREAKING HYPHEN). Added `_normalize_dashes` (maps U+2011/U+2013/U+2014/U+2012/U+2010/U+2212 to `-`) ahead of matching, added a regression test with the exact failure shape, and reconfirmed live: `cited_finding_ids == ['finding-0001', 'finding-0002', 'finding-0003']`, `untraceable_finding_ids == []`.
- **Impact if unfixed:** the traceability check is a safety mechanism (catch the model citing findings that don't exist). A regex that silently extracts zero citations from a narrative that clearly discusses real findings doesn't make the narration wrong, but it makes the *check* unable to do its job on a sizeable fraction of real responses -- an untraceable claim in that same response would also have gone uncaught, not because it was untraceable, but because the id matcher failed to engage at all.
- **Disposition:** fixed and reconfirmed by induction, not just by the new unit test.

### L15-CF-02 — Confirmation/audit digest mismatch is detected, not silently trusted

**Severity:** none **Epistemic level:** CODE FACT **Bucket:** hardening (prevents a real misattribution class)

- **Evidence:** `compute_recommendations` compares `confirmation["source_audit_digest"]` to `audit["audit_digest"]`; on mismatch, `confirmation_digest_mismatch` is set `True` and every CANDIDATE finding for every skill falls back to `pending` regardless of what the stale confirmation said.
- **Why this matters:** without this check, re-running `audit_corpus` after a skill file changes (new finding ids, different findings) while reusing an old `confirm.json` would let a confirmed-REJECTED verdict from the old audit silently suppress a finding in the new one that happens to share an id by coincidence of ordering -- finding ids are positional (`finding-0001`, `finding-0002`, ...), not content-addressed, so this is a real, not hypothetical, misattribution path. Test: `test_confirmation_from_a_different_audit_is_not_trusted`.

## Discarded (non-exploitable) vectors

| Vector | Result | Why it failed |
|---|---|---|
| Model narrates a recommendation contradicting the given one | Does not corrupt the sealed result | `recommendation` field is copied pre-call, never overwritten (L15-CF-01) |
| Model cites a finding id for a *different* skill in the same corpus | Flagged as untraceable | `known_ids` is scoped to the one skill's own `confirmed_finding_ids ∪ pending_finding_ids`; a real id from a sibling skill is not in that set |
| KEEP skill accidentally sent to the model, risking an invented concern | Not reachable | `narrate_skill` returns a fixed string and never calls `executor.execute` when `recommendation == "KEEP"` (unit-tested) |

## Reproduction

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_recommendation_contract.py tests/test_narrator_contract.py
```

Live reproduction (requires `NEBIUS_API_KEY`):

```bash
PYTHONPATH=src python3 -m crucible.cli tests/fixtures/readme-demo --narrate
```

Observed 2026-10-01: `recommendation: MODIFY`, `cited_finding_ids: [finding-0001, finding-0002, finding-0003]`, `untraceable_finding_ids: []`, real Nemotron response via `nebius-token-factory`.

This closes local verification of L15's deterministic/narration split under
the stated threat model. It does not close: model behavior under
adversarial prompt injection embedded in the skill text itself (the
findings' `evidence` strings come from the audited skill, which is
untrusted input the model reads -- not tested here), or stability of
citation extraction across other models/providers that may use yet other
dash conventions or id-formatting quirks.

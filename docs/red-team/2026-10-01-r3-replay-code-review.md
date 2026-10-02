# R3 offline oracle replay — code review

**Date:** 2026-10-01  **Method:** static adversarial review  
**Scope:** `oracle_replay.py`, `oracle_replay_cli.py`, and their replay-bundle/oracle callers.  
**Base:** `8ee55207aa91febd3d1bc835dabb2d27120ca745` plus the uncommitted R3 changes.  
**Status:** local negative controls executed; no real provider request was made.

## Threat model

- An attacker can supply or alter a replay bundle, including recomputing its public SHA-256 seals.
- The attacker cannot modify the installed Crucible code or Python runtime during the replay operation.
- The attacker cannot make the replay result authenticate a provider, endpoint, model identity, or the truth of the retained model response.

## Epistemic legend

CODE FACT · PLAUSIBLE HYPOTHESIS · CONFIRMED BY INDUCTION · FALSIFIED

## Executive summary

| ID | Severity | Level | Module | Finding |
|---|---|---|---|---|
| R3-CF-01 | None | CODE FACT | `oracle_replay.py` | Replay compares property statuses from retained response text; it does not replay L7 repair acceptance. |
| R3-CF-02 | None | CODE FACT | replay bundle boundary | A self-seal establishes byte consistency, not provider origin or response truth. |

No software vulnerability is confirmed by this code-only review.

## Findings

### R3-CF-01 — Observation agreement is not repair acceptance

**Severity:** none  **Epistemic level:** CODE FACT  **Bucket:** implementation scope

- **Surprise / expectation:** the construction checkpoint says “decision replay,” which can be read as replaying the L7 repair accept/reject outcome.
- **Evidence:** `_run` reports `MATCH`, `DIVERGED`, or `NOT_REPLAYABLE` after comparing stored and recomputed per-property statuses. The bundle schema has no L7 repair acceptance policy or repair-loop inputs. The R3 docs explicitly state that this result does not replay L7 acceptance.
- **Impact:** the result can reproduce the oracle's historical property statuses, but cannot independently reconstruct a repair-loop decision.
- **Disposition:** do not claim L7 decision replay from this result. If the R3 exit gate requires it, define a separately versioned decision input before extending the schema.

### R3-CF-02 — A self-sealed bundle does not establish provider origin

**Severity:** none under the stated threat model  **Epistemic level:** CODE FACT  **Bucket:** trust-model limitation

- **Evidence:** bundle validation checks SHA-256 seals and cross-links. It does not verify a provider signature or authenticated acquisition chain.
- **Disposition:** provider authenticity is explicitly outside the contract. A matching replay means “these statuses follow from these retained bytes under this local oracle,” not “the named provider produced these bytes.”

## Discarded vectors

| Vector | Result | Basis |
|---|---|---|
| Bundle with blocked/truncated/missing observations reaching the oracle | FALSIFIED under the tested local fixture | `test_incomplete_capture_is_not_sent_to_oracle` patches the oracle to fail if called; replay returns `NOT_REPLAYABLE`. |
| Resealed tampered observation passing exact replay | FALSIFIED under the tested local fixture | `test_resealed_observation_tampering_is_reported_as_divergence` reports `DIVERGED`; the hand mutation below makes it fail. |

## Induction and test integrity

**Prediction (before mutation):** if replay copies `recorded_status` into both
sides of the comparison, resealed tampering will incorrectly return `MATCH` and
the negative control will fail.

**Mutation and observation:** the mutation replaced the recomputed lookup with
the recorded lookup in `_replay_run`. The following command failed as predicted:

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_oracle_replay.py::test_resealed_observation_tampering_is_reported_as_divergence
```

Observed failure: expected `DIVERGED`, got `MATCH`. The mutation was restored.

After restoration, the focused local contract set passed:

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_oracle_replay.py tests/test_replay_bundle_contract.py tests/test_capture_bundle.py tests/test_replay_cli.py
```

Observed: **87 passed**, Python 3.12.3. The new test module SHA-256 is
`d5e9ba38cbda5f0f5d401c890e52cedeab913b9605b44fbebb06ae941726071b`.
The tests use a fake HTTP boundary and invoke no live provider. They cover
oracle mismatch refusal, observation tampering after resealing, incomplete
response refusal, explicit re-evaluation under a changed identity, v1 reading,
result sealing, historical-bundle preservation, and offline CLI behavior.

R3's local replay gate is closed for property-observation agreement under the
stated trust assumptions. It does not close provider authenticity, L7 repair
acceptance replay, or integrated release verification.

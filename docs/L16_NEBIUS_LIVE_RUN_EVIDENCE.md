# L16 consolidation — live run evidence against Nebius/Nemotron

**Date:** 2026-10-03
**Base:** main @ 52e3815

L16 (`consolidation.py`) had been implemented and tested only against
test-double proposers (`NaiveConcatProposer`, `GenericMergeProposer`,
`BlockedProposer`) — never against the real `LLMConsolidationProposer`
(Nebius/Nemotron). The coverage threshold (`_COVERAGE_THRESHOLD =
Fraction(1, 2)`) was, per ADR-0020, "a reasoned starting point, not a
measured one." This document records the first real runs and the first
measurement.

## What was run

All three runs used the real `NEBIUS_API_KEY` (no mock, no test-double
proposer). Raw output is preserved in
[`evidence/2026-10-03-l16-consolidation-live-run/`](evidence/2026-10-03-l16-consolidation-live-run/).

| Run | Scenario | Artifact | Result |
|---|---|---|---|
| 1 | 2-skill cluster (built-in `CONSOLIDATION_FIXTURE`) | [`run1-two-skill-merge.json`](evidence/2026-10-03-l16-consolidation-live-run/run1-two-skill-merge.json) | `ACCEPTED`, 4.9s |
| 2 | 3-skill cluster + one external `## Composes with` reference | [`run2-three-skill-merge-with-external-rewrite.json`](evidence/2026-10-03-l16-consolidation-live-run/run2-three-skill-merge-with-external-rewrite.json) | `ACCEPTED`, 5.4s, reference rewritten |
| 3 | 2-skill cluster, each with one genuinely distinct check (coverage measurement) | [`run3-distinct-checks-coverage-measurement.json`](evidence/2026-10-03-l16-consolidation-live-run/run3-distinct-checks-coverage-measurement.json) | `ACCEPTED`, 0 coverage gaps |

Model: `nvidia/nemotron-3-super-120b-a12b` via `nebius-token-factory`, same
as every other live-run executor in this project.

## Run 1: baseline merge

`retry-a` / `retry-b` (the module's own built-in fixture, near-identical
retry-budget skills). Nemotron proposed `bounded-retry`, keeping the one
shared rule and check verbatim. Deterministic gate: redundancy gone,
0 coverage gaps, 0 new findings. `ACCEPTED`.

## Run 2: 3-skill cluster + external reference

`retry-a`/`retry-b`/`retry-c` (near-identical, Jaccard 11/13 pairwise) plus
`external-caller`, which has `## Composes with\n- retry-a`. All three
redundancy pairs confirmed; `find_redundancy_clusters` correctly grouped
all three into one component (not three separate pairs). Nemotron
proposed `bounded-retry` (independently named, same idea as run 1).
`find_external_references` found `external-caller`'s section-heading
reference; `rewrite_external_references` rewrote the bullet from
`- retry-a` to `- bounded-retry` in place. Re-audit: redundancy gone, 0
coverage gaps, 0 new findings (including no `BROKEN_REFERENCE` on
`external-caller` — confirming the rewrite actually kept the reference
resolved). `ACCEPTED`.

## Run 3: coverage measurement with genuinely distinct checks

The open methodological question from ADR-0020: is `1/2` a reasonable
coverage bar on a *real* merge, not just a hand-written test-double's
output? `retry-a` and `retry-b` share three rules verbatim (budget,
idempotency, backoff) but each has one check the other does NOT have
(`check_backoff.sh` only in `retry-a`, `check_logging.sh` only in
`retry-b`). This is the shape that could plausibly make an LLM drop a
"non-shared" item during a merge.

Nemotron's proposed `retry-unified` kept **all three shared rules and
both distinct checks** — nothing dropped. The coverage gate (every
original rule/check needs >= 1/2 Jaccard overlap against some rule/check
in the merge) measured 0 gaps against this real output.

**What this does and does not establish:** one real model, one prompt,
two inputs, zero gaps found is evidence the threshold is not
*obviously* miscalibrated for this shape of input — it is not evidence
the threshold is correctly calibrated in general. A gap-producing case
was not found in this session because this run's merge happened not to
drop anything, not because the gate was exercised against a real
failure. Measuring the threshold properly needs either a larger sample
of real merges or a adversarial prompt designed to tempt the model into
dropping content — neither was done here. The gate's REJECT path is
still verified only by the test-double-based tests in
`tests/test_consolidation_contract.py` (`test_coverage_gap_rejects_merge`),
which is sound as a logic check but not evidence about real model
behavior.

## What this evidence establishes, and what it does not

**Establishes:** the full L16 pipeline — clustering, external-reference
detection and rewrite, proposal, deterministic re-audit, coverage check,
novelty check — runs end to end against the real Nebius/Nemotron API, not
just mocked. `LLMConsolidationProposer`'s JSON-object prompt format
(`{"name": ..., "text": ...}`) round-trips correctly against the real
model's output with no parse failures across 3 calls. The external-
reference rewrite was exercised against a real LLM-proposed merge name
(not a hand-picked test-double name) and still resolved correctly.

**Does not establish:** behavioral stability across model versions or
providers (same known limitation as every other live-run executor in this
project), batch mode (`--consolidate-all`/`run_consolidation_batch`)
against the real API (not re-run here, same risk profile as the already-
tested single-cluster path since it reuses `_run_gate_for_cluster`
verbatim, but not independently confirmed live), a case where the real
model actually drops content and the coverage gate catches it (not
observed in this session), or anything about cost/rate-limit behavior
under sustained use across many clusters.

## Key handling

Same `NEBIUS_API_KEY` as the earlier L1-L7 live run (see
`docs/NEBIUS_LIVE_RUN_EVIDENCE.md`), already present in this repo's `.env`
(gitignored, never committed — verify with `git check-ignore -v .env`).

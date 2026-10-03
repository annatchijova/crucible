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

All five runs used the real `NEBIUS_API_KEY` (no mock proposer; runs 1-4
used `--mock-confirm`-equivalent hand-built confirmation dicts to isolate
the consolidation step, run 5 used the real confirmation executor too).
Raw output is preserved in
[`evidence/2026-10-03-l16-consolidation-live-run/`](evidence/2026-10-03-l16-consolidation-live-run/).

| Run | Scenario | Artifact | Result |
|---|---|---|---|
| 1 | 2-skill cluster (built-in `CONSOLIDATION_FIXTURE`) | [`run1-two-skill-merge.json`](evidence/2026-10-03-l16-consolidation-live-run/run1-two-skill-merge.json) | `ACCEPTED`, 4.9s |
| 2 | 3-skill cluster + one external `## Composes with` reference | [`run2-three-skill-merge-with-external-rewrite.json`](evidence/2026-10-03-l16-consolidation-live-run/run2-three-skill-merge-with-external-rewrite.json) | `ACCEPTED`, 5.4s, reference rewritten |
| 3 | 2-skill cluster, each with one genuinely distinct check (coverage measurement) | [`run3-distinct-checks-coverage-measurement.json`](evidence/2026-10-03-l16-consolidation-live-run/run3-distinct-checks-coverage-measurement.json) | `ACCEPTED`, 0 coverage gaps |
| 4 | `run_consolidation_batch`, 2 independent clusters (retry + format) + external reference, Python API | [`run4-batch-mode-two-clusters.json`](evidence/2026-10-03-l16-consolidation-live-run/run4-batch-mode-two-clusters.json) | `COMPLETED`, both `ACCEPTED`, 7.0s total |
| 5 | Same 2-cluster scenario through the actual `crucible --consolidate-all` CLI, with the REAL confirmation executor too (not just the consolidation step) | [`run5-cli-consolidate-all-full-real-pipeline.json`](evidence/2026-10-03-l16-consolidation-live-run/run5-cli-consolidate-all-full-real-pipeline.json) | `COMPLETED`, both `ACCEPTED` |

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

## Run 4: batch mode, two independent clusters (Python API)

The remaining open item from the batch-mode addendum: `run_consolidation_batch`
had never been run against the real API, only test-double proposers. A
5-skill corpus with two unrelated redundancy pairs (`retry-a`/`retry-b`,
`format-a`/`format-b`) plus `external-caller` (composes with `retry-a`).

`find_redundancy_clusters` correctly found two separate clusters (not one
merged group — the pairs share no tokens with each other). The batch
processed both sequentially against the real model: `format-a`/`format-b`
→ `currency-format`, then `retry-a`/`retry-b` → `bounded-retry`, with
`external-caller`'s reference rewritten to `bounded-retry` in the same
pass. Total wall time 7.0s for two real LLM calls plus three re-audits.
Both `ACCEPTED`, `batch_status: COMPLETED`, final corpus: `bounded-retry`,
`currency-format`, `external-caller` (5 skills down to 3).

## Run 5: the actual CLI, confirmation included

Runs 1-4 called `run_consolidation`/`run_consolidation_batch` directly in
Python with a hand-built confirmation dict, to isolate the consolidation
step from confirmation-layer calibration (as seen earlier: `MockConfirmExecutor`'s
80%-line-overlap heuristic rejects these same near-duplicate pairs even
though the real `SEMANTIC_REDUNDANCY` Jaccard check accepts them above
2/3 token overlap -- the two layers measure similarity differently on
purpose, which is a real, separate finding worth remembering when
`--mock-confirm` is used for anything resembling this corpus shape).

Run 5 drops `--mock-confirm` entirely and runs the real
`crucible --consolidate-all` CLI command end to end against the same
5-skill corpus: real `NebiusConfirmExecutor` for confirmation, real
`LLMConsolidationProposer` for the merge proposals, through the actual
argparse/CLI code path a user would type, not a Python harness. Same
result as run 4: both clusters `ACCEPTED`, same final skill names. This
is the first time every layer of L16 ran live, through the CLI, in one
command.

## What this evidence establishes, and what it does not

**Establishes:** the full L16 pipeline — clustering, external-reference
detection and rewrite, proposal, deterministic re-audit, coverage check,
novelty check — runs end to end against the real Nebius/Nemotron API, not
just mocked, in both single-cluster (`--consolidate`) and batch
(`--consolidate-all`) modes, and through the actual CLI command a user
would run (run 5), not only the Python API. `LLMConsolidationProposer`'s
JSON-object prompt format (`{"name": ..., "text": ...}`) round-tripped
correctly across all 5 calls with no parse failures. The external-
reference rewrite was exercised against real LLM-proposed merge names
(not hand-picked test-double names) in both a single-cluster run and a
batch run, and resolved correctly both times. `find_redundancy_clusters`
correctly kept two unrelated pairs as two separate clusters rather than
merging them into one, confirmed against real confirmation verdicts.

**Does not establish:** behavioral stability across model versions or
providers (same known limitation as every other live-run executor in this
project), a case where the real model actually drops content and the
coverage gate catches it in REJECT (not observed in any of the 4 merge
attempts across this session — every real merge happened to be clean),
or anything about cost/rate-limit behavior under sustained use across
many clusters (the largest batch tried here was 2 clusters).

A real, separate finding worth recording: `MockConfirmExecutor`'s
80%-line-overlap heuristic and the real `SEMANTIC_REDUNDANCY` check's
2/3 token-Jaccard threshold do not agree on every pair -- the near-
duplicate fixtures used in runs 4 and 5 clear the real token-based bar
comfortably but fail the mock's line-based one (differing name/heading
lines are enough to drop line overlap under 80% even when token overlap
stays above 2/3). `--mock-confirm` is a deterministic stand-in for
testing the confirmation *harness* without network access, not a
calibration match for the real detector; this is worth knowing before
reaching for `--mock-confirm` to sanity-check a corpus shape, rather than
discovering it as a confusing `NO_CLUSTERS` result.

## Key handling

Same `NEBIUS_API_KEY` as the earlier L1-L7 live run (see
`docs/NEBIUS_LIVE_RUN_EVIDENCE.md`), already present in this repo's `.env`
(gitignored, never committed — verify with `git check-ignore -v .env`).

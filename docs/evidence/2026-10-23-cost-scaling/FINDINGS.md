# Audit cost against corpus size

**Date:** 2026-10-23  **Branch:** `main`  **Base:** `094a087`
**Corpus:** `mukul975/Anthropic-Cybersecurity-Skills` @ `54a7988`, sealed
`TUNING_CONSUMED`. Subsamples are the first *n* skills by sorted relative
path, each with its own `corpus-provenance/v1` record.
**Status:** observation only. These numbers gate nothing and are not
reproducible on another machine or under another load.

## Why this exists

Execution cost at scale was the one requested measurement absent from both
the code and the build plan. Before this record, `grep -E
'elapsed|perf_counter|duration_ms'` over `src/` returned nothing.

## Measured series

Three runs per size; the minimum of each is shown. Full records with every
run, both extremes, and the corpus and audit digests they are bound to are in
[`cost-series.json`](cost-series.json).

| Skills | Wall (min) | ms per skill | Findings | Graph edges |
|---|---|---|---|---|
| 25 | 63 ms | 2.52 | 38 | 0 |
| 50 | 125 ms | 2.50 | 70 | 0 |
| 100 | 284 ms | 2.84 | 157 | 0 |
| 200 | 667 ms | 3.34 | 335 | 0 |
| 400 | 1471 ms | 3.68 | 542 | 0 |
| 818 | 3769 ms | 4.61 | 1056 | 0 |

Cost per skill rises from 2.52 to 4.61 ms. Each doubling of corpus size costs
roughly 2.2 to 2.5 times as much, against 2.0 for linear scaling.

## Where the superlinearity is

Per-stage measurement, one run each:

| Skills | compile | audit | graph |
|---|---|---|---|
| 100 | 220 ms | 69 ms | 1 ms |
| 200 | 463 ms | 206 ms | 4 ms |
| 400 | 924 ms | 564 ms | 7 ms |
| 818 | 1910 ms | 1668 ms | 15 ms |

Compilation doubles when the corpus doubles (2.10, 2.00, 2.07) and is linear.
The auditor costs 2.7 to 3.0 times as much per doubling, so it is
superlinear, and it overtakes compilation between 400 and 818 skills.

The cause is in the code, not inferred from the curve.
`auditor.py:_check_semantic_redundancy` (line 525) compares every skill pair:
818 skills is 334,153 comparisons, each one Jaccard overlap over precomputed
token sets. That is exactly the pair count an external review cited as the
reason per-file scanning cannot answer composition. The pair space is real
and it is traversed here -- it is simply cheap per pair at this size.

Two further pairwise checks cost nothing on this corpus for a different
reason. `_check_normative_conflict` (line 394) and
`_check_conditional_contradiction` (line 671) both require a rule `subject`,
and only 1 of 818 skills yields one, so both compare zero pairs. Their cost
would change substantially on a corpus where rule extraction succeeds; see
[the rule-extraction yield record](../2026-10-23-rule-extraction-yield/FINDINGS.md).

## Projection, and why it is weak

Extrapolating the auditor's observed ~2.85x per doubling, 3,000 skills would
cost roughly 20 s of audit and 10,000 skills roughly 3 minutes. Treat this as
an order of magnitude only: six sizes on one machine cannot separate n log n
from n^1.5 from a quadratic term with a small constant, and the dominant
quadratic check is sensitive to token-set size, which varies by corpus.

## Limits of this record

- One machine, one load, three runs per size, no isolation from the
  filesystem cache. `cost-record/v1` declares `determinism_level:
  "observation"` for this reason, retains every run, and reports only minimum
  and maximum, never a mean.
- Subsamples are the first *n* skills by sorted path, so they are
  deterministic and reproducible but not random. Any content-correlated
  ordering in the corpus biases the series.
- The graph column is 0 at every size because this corpus declares no
  relations. Edge-construction cost is therefore unmeasured here, not shown
  to be negligible.
- A cost record carries no authority over any finding, verdict or gate, and
  agreement between two cost records is not evidence of correctness.

## Reproducing

```bash
python docs/evidence/2026-10-23-cost-scaling/measure_scaling.py <corpus-root> <out-dir> 3
```

The script refuses to measure a corpus whose worktree is not clean, and seals
each subsample's own corpus provenance alongside its cost record.

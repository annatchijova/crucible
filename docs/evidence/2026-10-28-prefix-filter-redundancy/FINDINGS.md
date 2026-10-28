# SEMANTIC_REDUNDANCY without comparing every pair, with identical output

**Date:** 2026-10-28
**Answers:** L6 in [`INVESTIGAR-CRUCIBLE.md`](../../../INVESTIGAR-CRUCIBLE.md), and
the open point in the [RU/ZH sweep review](../2026-10-28-ru-zh-research-sweep/FINDINGS.md#l6-reproducible-no-es-lo-mismo-que-equivalente).
**Code:** `auditor.py:_prefix_filter_candidates`, used by
`_check_semantic_redundancy`. **Tests:** `tests/test_prefix_filter_contract.py`.

## The constraint

The sweep proposed MinHash with a fixed seed plus LSH banding. That gives
bit-for-bit reproducibility, but a banded LSH drops qualifying pairs by design:
which findings appear would depend on `num_perm`, `b` and `r`. The audit would
be reproducible and still not the same audit.

## What was done

Exact prefix filtering for set-similarity joins. Every token set is ordered by
one global order (rarest token first, ties broken by the token). If
`J(x, y) >= t`, then `x` and `y` share at least `ceil(t * |x|)` tokens. Two
sets that share `a` tokens in the same order must share one within the first
`|x| - a + 1` tokens of each. Indexing only those prefixes yields every pair
that can qualify, and the existing exact `Fraction` Jaccard still makes every
decision. There is no seed, no hash and no float. `ceil` is computed with
integer arithmetic on the threshold's numerator and denominator.

## Result

[`compare_prefix_filter.py`](compare_prefix_filter.py) audits each corpus twice,
once with every pair and once with the prefix filter, and compares the full
`audit_digest`.

| Corpus | Skills | Findings | Pairs compared, all → prefix | Check time, all → prefix | Whole audit, all → prefix | Digest |
|---|---|---|---|---|---|---|
| `vantaflow` @ `f88a34d0f75e` | 692 | 337 | 239,086 → 4,131 | 1.28 s → 0.06 s | 2.19 s → 0.86 s | identical |
| `mukul975` @ `54a7988` | 818 | 1 | 334,153 → 10,653 | 2.07 s → 0.13 s | 3.03 s → 1.28 s | identical |
| `tests/fixtures/readme-demo` | 1 | 0 | 0 → 0 | — | — | identical |

Times are from one container, best of three for the whole audit. They show the
size of the change, not a benchmark.

The tests compare candidates against brute force on 60 near-threshold
synthetic corpora at four thresholds, cover a pair sitting exactly on 2/3, and
check that the output order matches the old nested loop. Shortening the prefix
by one token turns two of the three tests red.

## Limits

- The two `HELDOUT_SEALED` corpora were not run. Their seal is for evaluation,
  and this change is checked by digest equality, which does not need them.
- Filtering prunes pairs; it does not change the worst case. A corpus where
  every skill shares the same rare tokens still compares nearly every pair.
  Neither measured corpus is like that.
- The rest of the auditor is now most of the audit time. The superlinearity in
  the [cost record](../2026-10-23-cost-scaling/FINDINGS.md) is reduced here,
  not re-measured across corpus sizes.

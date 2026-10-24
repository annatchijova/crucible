# A reduced fraction hid the denominator, and produced a wrong hypothesis

**Date:** 2026-10-23  **Branch:** `main`  **Base:** `25731b5`
**Status:** defect reproduced and fixed; the hypothesis it caused is refuted.

## How this started

Earlier today a record claimed that `SEMANTIC_REDUNDANCY`'s 337 findings on
the `vantaflow` corpus were probably driven by shared boilerplate rather than
by genuine duplication (V-02). That claim was an inference, written down
without measuring the pairs. This record is the measurement, and it reverses
it.

## Firstness — what was observed

`SEMANTIC_REDUNDANCY` counts across the five corpora:

| Corpus | Skills | SEMANTIC_REDUNDANCY |
|---|---|---|
| author | 101 | 0 |
| `mukul975` | 818 | 1 |
| `vantaflow` | 692 | **337** |
| `nimadorostkar` | 138 | 0 |
| `TerminalSkills` | 1057 | 1 |

A sampled finding read:

```text
lexical Jaccard overlap 1/1 with psy-addiction-awareness-log (threshold 2/3)
```

## Secondness — the misreading that followed

`1/1` was read as a one-token union: a degenerate pair where both fingerprints
collapsed to a single token. That supported the boilerplate hypothesis, and it
was wrong. The two skills have **58 tokens each and identical token sets**.
`Fraction(58, 58)` reduces to `1`, and the evidence printed the reduced
fraction.

The same reduction applies throughout. A finding reported `17/22`; the raw
counts are `34/44`. A reader cannot recover how much text was compared from
any of these strings.

This matters because the threshold is `2/3`. A pair sitting exactly on it
could be 2 shared tokens of 3, which is a coincidence, or 400 of 600, which is
substantive. The artifact could not tell them apart, in a project whose stated
discipline is to keep denominators visible.

## Thirdness — what was actually happening

Measured over all 337 reported pairs:

| Property | Result |
|---|---|
| name pattern `X` / `<prefix>-X` | **337 of 337** |
| byte-identical fingerprints | 43 |
| raw union >= 40 tokens | 211 |
| raw union < 10 tokens | **0** |
| raw union min / median / max | 30 / 43 / 116 |

`vantaflow` publishes each skill twice, once under a bare name and once under
a category-prefixed one — `allergy-reaction-log` and
`health-allergy-reaction-log`, `anxiety-debrief` and `psy-anxiety-debrief` —
and the check found all 337. These are true positives with substantive token
unions, which makes this the strongest demonstrated performance of
`SEMANTIC_REDUNDANCY` on a real corpus rather than a false-positive cluster.

Note what the corpus-level duplicate-name check could not catch: these pairs
have *different* declared names, so `compile_corpus`'s name-collision refusal
([ADR-0026](../../decisions/0026-duplicate-skill-name-coverage.md)) passes
them through. Renamed republication is invisible to a name check and visible
to a lexical one, which is a point in favour of keeping both.

## The second defect: evidence prose as a parsed interface

Fixing the evidence string broke 12 consolidation tests. `confirm.py`
parses the auditor's human-readable prose with
`r"lexical Jaccard overlap (\d+/\d+) with (\S+) "` to recover the pair, so
rewording the message stops the L2.5 confirmation layer finding clusters —
reported as `NO_CLUSTERS`, which looks like a corpus with no redundancy rather
than a broken parse.

The tests caught it, which is what they are for. Both sites now carry a
`COUPLING:` comment naming the other, and
`tests/test_redundancy_evidence_denominator.py` asserts that the confirmation
layer can still recover the pair, so the next rewording fails loudly.

The architecturally correct fix is to carry the pair and the counts in
structured finding fields instead of prose. That is a finding-schema change
rippling through the viewer, human output, report, consolidation and
confirmation paths, and it is deliberately deferred: the build is green six
days from a submission, and a comment plus a test closes the regression at a
fraction of the risk.

## Fix applied

The evidence now reads
`lexical Jaccard overlap 34/44 tokens (ratio 17/22) with …`: the raw shared
and compared counts, beside the exact reduced ratio. Still no float — the
comparison keeps using `Fraction`, which was always correct.

No version bump. The `preconditions` and finding schemas, their field names,
types and statuses are unchanged; only the evidence text differs, and the
repository has changed check vocabularies and finding counts before without
bumping `AUDIT_VERSION`, which signals contract changes.

## Limits

- The 337 pairs are adjudicated here only by name pattern and token identity.
  That is strong evidence of republication, and it is not a human review of
  whether each pair is methodologically redundant.
- One corpus. `vantaflow` is `TUNING_CONSUMED`, so nothing here is a
  generalization claim, and nothing was tuned against the two held-out
  corpora.
- The lesson is about method, not about this check: V-02 was written from an
  inference that looked sufficient. The cost of not measuring first was a
  published claim that had to be retracted the same day.

"""The prefix filter must generate every pair that can reach the threshold.

It is an optimisation of SEMANTIC_REDUNDANCY, not a new check: any pair it
skips that qualifies would silently remove a finding.
"""

from __future__ import annotations

import itertools
import random
from fractions import Fraction

from crucible.auditor import _SEMANTIC_THRESHOLD, _jaccard, _prefix_filter_candidates


def _qualifying(token_sets, threshold):
    return [
        (i, j)
        for i, j in itertools.combinations(range(len(token_sets)), 2)
        if _jaccard(token_sets[i], token_sets[j]) >= threshold
    ]


def _corpus(seed: int, size: int) -> list[frozenset[str]]:
    # Test data only: a fixed seed, so the corpus is the same on every run.
    rng = random.Random(seed)
    vocabulary = [f"t{n}" for n in range(40)]
    sets = []
    for _ in range(size):
        if sets and rng.random() < 0.4:
            # Perturb an earlier set so that many pairs sit near the threshold.
            base = set(rng.choice(sets))
            for _ in range(rng.randint(0, 3)):
                if base and rng.random() < 0.5:
                    base.discard(rng.choice(sorted(base)))
                else:
                    base.add(rng.choice(vocabulary))
            sets.append(frozenset(base) or frozenset({"t0"}))
        else:
            sets.append(frozenset(rng.sample(vocabulary, rng.randint(1, 12))))
    return sets


def test_every_qualifying_pair_is_a_candidate() -> None:
    """Invariant: candidates are a superset of the pairs at or above the
    threshold, for several thresholds and many near-threshold corpora.
    Mutation: shorten the prefix by one token -> some qualifying pair is
    missed -> red."""
    for seed in range(60):
        token_sets = _corpus(seed, 40)
        for threshold in (_SEMANTIC_THRESHOLD, Fraction(1, 2), Fraction(1, 3), Fraction(9, 10)):
            candidates = set(_prefix_filter_candidates(token_sets, threshold))
            missing = set(_qualifying(token_sets, threshold)) - candidates
            assert not missing, (seed, threshold, sorted(missing)[:3])


def test_a_pair_exactly_on_the_threshold_is_kept() -> None:
    """Boundary: 2 shared of 3 total is exactly 2/3 and must be generated."""
    token_sets = [frozenset({"a", "b"}), frozenset({"a", "b", "c"})]
    assert _jaccard(*token_sets) == _SEMANTIC_THRESHOLD
    assert _prefix_filter_candidates(token_sets, _SEMANTIC_THRESHOLD) == [(0, 1)]


def test_candidates_are_sorted_and_do_not_depend_on_input_set_order() -> None:
    """Invariant: the output is the (i, j)-sorted list the old nested loop
    visited, and set iteration order cannot change it."""
    token_sets = _corpus(7, 30)
    candidates = _prefix_filter_candidates(token_sets, _SEMANTIC_THRESHOLD)
    assert candidates == sorted(candidates)
    assert all(i < j for i, j in candidates)
    rebuilt = [frozenset(sorted(s, reverse=True)) for s in token_sets]
    assert _prefix_filter_candidates(rebuilt, _SEMANTIC_THRESHOLD) == candidates

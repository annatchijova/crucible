"""Measure how large a family of mergeable skills real corpora contain.

Three lexical similarity objects, each over every skill pair (exact, through
the auditor's prefix filter where it applies):

- scope: Jaccard over the description alone, the text that decides when an
  agent loads a skill, at 2/3, 1/2 and 2/5; families are connected components.
- containment: the share of a smaller skill's fingerprint tokens present in a
  larger one, at 4/5 and 2/3, for skills of at least 20 tokens; a family is a
  larger skill and every smaller skill it contains.
- whole skill: the shipped SEMANTIC_REDUNDANCY fingerprint, for reference.

Usage:
    python docs/evidence/2026-10-28-n-to-1-families/measure_families.py CORPUS_DIR [...]
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from fractions import Fraction

from crucible.auditor import _jaccard, _prefix_filter_candidates, _skill_token_set, _tokenize
from crucible.compiler import ON_DUPLICATE_SKIP, compile_corpus
from crucible.graph import _find_components


def _components(names, token_sets, threshold):
    edges, nodes = [], set()
    for i, j in _prefix_filter_candidates(token_sets, threshold):
        if token_sets[i] and token_sets[j] and _jaccard(token_sets[i], token_sets[j]) >= threshold:
            edges.append({"source": names[i], "target": names[j], "resolved": True})
            nodes.update((names[i], names[j]))
    return _find_components(edges, nodes)


def _containment_hubs(token_sets, threshold, min_tokens=20):
    index = defaultdict(list)
    for i, tokens in enumerate(token_sets):
        for token in tokens:
            index[token].append(i)
    hubs = defaultdict(list)
    for i, small in enumerate(token_sets):
        if len(small) < min_tokens:
            continue
        shared = Counter(j for token in small for j in index[token] if j != i)
        for j, count in shared.items():
            if len(token_sets[j]) > len(small) and Fraction(count, len(small)) >= threshold:
                hubs[j].append(i)
    return hubs


def main(roots):
    for root in roots:
        ir = compile_corpus(root, on_duplicate_name=ON_DUPLICATE_SKIP)
        names = [s["identity"]["name"] for s in ir["skills"]]
        print(f"{root}: {len(names)} skills")
        whole = [_skill_token_set(s) for s in ir["skills"]]
        scope = [_tokenize(s.get("metadata", {}).get("description", "")) for s in ir["skills"]]
        comps = _components(names, whole, Fraction(2, 3))
        print(f"  whole skill 2/3: largest family {max(map(len, comps), default=0)}, "
              f"sizes {dict(sorted(Counter(map(len, comps)).items()))}")
        for t in (Fraction(2, 3), Fraction(1, 2), Fraction(2, 5)):
            comps = _components(names, scope, t)
            print(f"  scope {t}: largest family {max(map(len, comps), default=0)}, "
                  f"sizes {dict(sorted(Counter(map(len, comps)).items()))}")
        for t in (Fraction(4, 5), Fraction(2, 3)):
            hubs = _containment_hubs(whole, t)
            largest = max((len(v) + 1 for v in hubs.values()), default=0)
            print(f"  containment {t}: largest family {largest} (hub + contained), "
                  f"{len(hubs)} hubs")


if __name__ == "__main__":
    main(sys.argv[1:])

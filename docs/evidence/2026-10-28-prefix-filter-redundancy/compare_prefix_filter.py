"""Compare the prefix-filtered SEMANTIC_REDUNDANCY check with all pairs.

Audits each corpus twice: once as shipped, once with the candidate generator
replaced by every (i, j) pair, which is the pre-2026-10-28 behaviour. Prints
the audit digests, the SEMANTIC_REDUNDANCY count, how many pairs each run
compared, and the time spent in the check.

Usage:
    python docs/evidence/2026-10-28-prefix-filter-redundancy/compare_prefix_filter.py CORPUS_DIR [...]
"""

from __future__ import annotations

import sys
import time

from crucible import auditor
from crucible.compiler import ON_DUPLICATE_SKIP, compile_corpus

_prefix = auditor._prefix_filter_candidates


def _all_pairs(token_sets, threshold):
    return [(i, j) for i in range(len(token_sets)) for j in range(i + 1, len(token_sets))]


def _run(ir, generator):
    compared = []

    def counting(token_sets, threshold):
        pairs = generator(token_sets, threshold)
        compared.append(len(pairs))
        return pairs

    auditor._prefix_filter_candidates = counting
    try:
        start = time.perf_counter()
        findings = auditor._check_semantic_redundancy(ir["skills"])
        elapsed = time.perf_counter() - start
        audit = auditor.audit_corpus(ir)
    finally:
        auditor._prefix_filter_candidates = _prefix
    return audit, findings, (compared[0] if compared else 0), elapsed


def main(roots: list[str]) -> int:
    status = 0
    for root in roots:
        ir = compile_corpus(root, on_duplicate_name=ON_DUPLICATE_SKIP)
        brute, brute_findings, brute_pairs, brute_s = _run(ir, _all_pairs)
        fast, fast_findings, fast_pairs, fast_s = _run(ir, _prefix)
        same = brute["audit_digest"] == fast["audit_digest"] and brute_findings == fast_findings
        status |= not same
        print(f"{root}: skills={len(ir['skills'])} semantic={len(fast_findings)} "
              f"pairs all={brute_pairs} prefix={fast_pairs} "
              f"check_seconds all={brute_s:.2f} prefix={fast_s:.2f} "
              f"identical={same} digest={fast['audit_digest'][:19]}")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

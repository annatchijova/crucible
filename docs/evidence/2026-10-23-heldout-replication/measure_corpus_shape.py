"""Report the extraction shape of one or more corpora, side by side.

This exists because the same table was rebuilt by hand three times on
2026-10-23 and one of those passes produced a claim that had to be retracted.
The columns are the ones that actually moved the conclusions: how many rules
were extracted, how many of them are *distinct* text, which modality routes
they came from, whether any carries a subject, and whether the composition
graph had anything to work with.

`distinct_rule_texts` is the column V-01 is about. A corpus can report 302
rules that are one boilerplate line repeated 302 times, which overstates its
distinct normative content by 302 to 1. The sealed audit artifact is not the
place for that figure -- `preconditions.corpus_inputs.rules` correctly counts
rule records, which is what a precondition question needs -- but any
cross-corpus comparison is misleading without it.

Nothing here is a quality measure. Every number is extractor output, and a
higher rule count is not a better corpus.

Usage:
    python measure_corpus_shape.py <corpus-root>[=label] ...
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from crucible.auditor import audit_corpus
from crucible.compiler import ON_DUPLICATE_SKIP, compile_corpus
from crucible.graph import build_composition_graph

MODAL_ROUTE = frozenset({
    "MUST", "MUST_NOT", "SHOULD", "SHOULD_NOT", "MAY",
    "REQUIRED", "SHALL", "SHALL_NOT", "RECOMMENDED", "OPTIONAL",
})


def shape(root: str, label: str) -> dict:
    # Skip duplicate names rather than refuse: a shape report should describe
    # what a corpus contains, and it records the exclusions it had to make.
    ir = compile_corpus(root, on_duplicate_name=ON_DUPLICATE_SKIP)
    audit = audit_corpus(ir)
    graph = build_composition_graph(ir, audit)
    skills = ir["skills"]
    rules = [rule for skill in skills for rule in skill["rules"]]
    texts = Counter(rule["text"].strip() for rule in rules)
    modality = Counter(rule["modality"] for rule in rules)
    return {
        "label": label,
        "skills": len(skills),
        "excluded": len(ir["excluded"]),
        "rules": len(rules),
        "distinct_rule_texts": len(texts),
        "largest_duplicate_rule_group": max(texts.values()) if texts else 0,
        "skills_with_a_rule": sum(1 for s in skills if s["rules"]),
        "rules_via_modal_route": sum(
            count for name, count in modality.items() if name in MODAL_ROUTE),
        "rules_with_a_subject": sum(1 for r in rules if r.get("subject")),
        "modality_mix": dict(modality.most_common()),
        "checks": sum(len(s["checks"]) for s in skills),
        "procedural_steps": sum(len(s["procedural_steps"]) for s in skills),
        "findings": audit["summary"]["total"],
        "abstained_checks": audit["preconditions"]["abstained_count"],
        "graph_edges": len(graph["edges"]),
        "graph_composition_outcome": graph["preconditions"]["composition"]["outcome"],
        "audit_digest": audit["audit_digest"],
    }


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    rows = []
    for spec in sys.argv[1:]:
        root, _, label = spec.partition("=")
        rows.append(shape(root, label or Path(root).name))

    header = (f"{'corpus':<22}{'skills':>7}{'rules':>7}{'distinct':>9}"
              f"{'dupmax':>7}{'modal':>7}{'subj':>6}{'checks':>7}"
              f"{'find':>6}{'abst':>6}{'edges':>7}")
    print(header)
    print("-" * len(header))
    for row in rows:
        print(f"{row['label'][:21]:<22}{row['skills']:>7}{row['rules']:>7}"
              f"{row['distinct_rule_texts']:>9}{row['largest_duplicate_rule_group']:>7}"
              f"{row['rules_via_modal_route']:>7}{row['rules_with_a_subject']:>6}"
              f"{row['checks']:>7}{row['findings']:>6}"
              f"{row['abstained_checks']:>6}{row['graph_edges']:>7}")
    print()
    for row in rows:
        if row["rules"] and row["distinct_rule_texts"] < row["rules"]:
            duplicated = row["rules"] - row["distinct_rule_texts"]
            print(f"{row['label']}: {duplicated} of {row['rules']} extracted rules "
                  f"repeat earlier text; the largest duplicate group holds "
                  f"{row['largest_duplicate_rule_group']}. A rule count alone "
                  f"overstates this corpus's distinct normative content.")
    print()
    print(json.dumps(rows, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()

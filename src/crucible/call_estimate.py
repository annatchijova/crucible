"""Upper bound on the model calls a narrated report will make, before making any.

A live report spends one provider call per confirmable candidate, per skill
narrated, per duplicate group merged, per targeted class rewritten, plus one
summary. Only the first is known before confirmation runs; the rest depend on
verdicts. This module audits the corpus (no model, no key) and returns, per
stage, a bound that the live run cannot exceed:

- confirmation: exact -- one call per CANDIDATE finding whose class has a
  confirmation prompt.
- narration: every skill that is not KEEP if every candidate were confirmed
  (a rejection can only turn a skill into KEEP, which is never narrated),
  plus one executive summary.
- consolidation: per connected component of SEMANTIC_REDUNDANCY candidate
  pairs, at most min(pairs, floor(size / 2)) groups -- groups are disjoint
  and need two members, and rejecting a pair can split a component.
- repairs: the largest sum of distinct repairable classes over ``limit``
  skills, since one call is made per targeted class.
"""

from __future__ import annotations

from typing import Any

from .auditor import audit_corpus
from .compiler import ON_DUPLICATE_ERROR, compile_corpus
from .confirm import _PROMPT_BUILDERS, _parse_semantic_redundancy_pair
from .graph import _find_components
from .ir import digest_payload
from .recommendation import compute_recommendations
from .repair_suggestions import NOT_REPAIRED_HERE

CALL_ESTIMATE_VERSION = "crucible-call-estimate/v1"

_CONFIRMABLE = frozenset(_PROMPT_BUILDERS) | {"SEMANTIC_REDUNDANCY"}


def estimate_model_calls(
    corpus_root: str,
    *,
    on_duplicate_name: str = ON_DUPLICATE_ERROR,
    with_consolidation: bool = False,
    with_repairs: bool = False,
    repair_limit: int = 10,
) -> dict[str, Any]:
    ir = compile_corpus(corpus_root, on_duplicate_name=on_duplicate_name)
    audit = audit_corpus(ir)
    findings = audit["findings"]
    names = [skill["identity"]["name"] for skill in ir["skills"]]

    confirmation = sum(
        1 for f in findings
        if f.get("epistemic_status") == "CANDIDATE" and f.get("class") in _CONFIRMABLE
    )

    everything_confirmed = {
        "source_audit_digest": audit["audit_digest"],
        "confirmations": [
            {"finding_id": f["id"], "verdict": "CONFIRMED"} for f in findings
        ],
    }
    worst = compute_recommendations(audit, everything_confirmed, names)
    narrated = sum(1 for s in worst["skills"].values() if s["recommendation"] != "KEEP")

    stages: dict[str, int] = {
        "confirmation": confirmation,
        "narration": narrated,
        "executive_summary": 1,
    }

    if with_consolidation:
        edges, nodes = [], set()
        for f in findings:
            pair = _parse_semantic_redundancy_pair(f)
            if pair is None:
                continue
            edges.append({"source": pair[0], "target": pair[1], "resolved": True})
            nodes.update(pair[:2])
        bound = 0
        for component in _find_components(edges, nodes):
            members = set(component)
            pairs = sum(1 for e in edges if e["source"] in members)
            bound += min(pairs, len(component) // 2)
        stages["consolidation"] = bound

    if with_repairs:
        classes_by_skill: dict[str, set[str]] = {}
        for f in findings:
            if f.get("class") in NOT_REPAIRED_HERE or not f.get("skill"):
                continue
            classes_by_skill.setdefault(f["skill"], set()).add(f["class"])
        largest = sorted((len(c) for c in classes_by_skill.values()), reverse=True)
        stages["repairs"] = sum(largest[:repair_limit])

    result: dict[str, Any] = {
        "schema_version": CALL_ESTIMATE_VERSION,
        "audit_digest": audit["audit_digest"],
        "skill_count": len(names),
        "max_calls_by_stage": stages,
        "max_calls_total": sum(stages.values()),
        "exact_stages": ["confirmation", "executive_summary"],
        "note": (
            "Upper bounds: no model was called. Confirmation is exact; the "
            "other stages depend on its verdicts and cannot exceed these values."
        ),
    }
    result["estimate_digest"] = digest_payload(result)
    return result

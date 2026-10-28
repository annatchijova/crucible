"""L15 final report assembly.

Runs L1 (compile) -> L2 (audit) -> L2.5/L12 (confirmation) -> L15
(recommendation + narration) for a corpus and seals the combined result as
one `crucible-final-report/v1` artifact. This is the single input the
Markdown, HTML, and PDF renderers (final_report_render.py) all consume --
mirroring the one-sealed-result-many-projections pattern this codebase
already uses for every other level.

This module only orchestrates; it does not re-implement any level's logic,
same discipline as report.py's L1-L7 composite.
"""

from __future__ import annotations

from typing import Any

from .auditor import audit_corpus
from .compiler import compile_corpus
from .confirm import ConfirmExecutor, confirm_candidates
from .ir import digest_payload
from .narrator import NarrationExecutor, narrate_skill
from .recommendation import compute_recommendations

FINAL_REPORT_VERSION = "crucible-final-report/v2"

_CONTRADICTION_CLASSES = ("NORMATIVE_CONFLICT", "CONDITIONAL_CONTRADICTION")

# Fixed, per-class statements of the methodological risk a contradiction
# carries. They are written here, not by the model, so the risk a reader is
# told about is the same for every corpus and every run.
CONTRADICTION_RISK = {
    "NORMATIVE_CONFLICT": (
        "An agent that loads both rules receives opposite obligations about "
        "the same subject and no declared priority between them. Which one it "
        "follows depends on load order or on what is most recent in its "
        "context, so the behaviour is not reproducible across sessions, and "
        "an audit of either skill alone will not reveal it."
    ),
    "CONDITIONAL_CONTRADICTION": (
        "When the stated condition holds, the two rules prescribe opposite "
        "guidance and nothing declares which one wins. The conflict is "
        "invisible in the common case and surfaces only when that condition "
        "is met, which is when the guidance matters."
    ),
}


def _rule_texts(ir: dict[str, Any]) -> dict[tuple[str, str], str]:
    return {
        (skill["identity"]["name"], rule["id"]): rule["text"]
        for skill in ir["skills"]
        for rule in skill.get("rules", [])
    }


def _skills_holding(ir: dict[str, Any], text: str) -> list[str]:
    return sorted({
        skill["identity"]["name"]
        for skill in ir["skills"]
        for rule in skill.get("rules", [])
        if rule["text"] == text
    })


def _corpus_sections(
    ir: dict[str, Any],
    audit: dict[str, Any],
    recommendations: dict[str, Any],
) -> dict[str, Any]:
    """The corpus-level part of the report: what no per-skill entry shows.

    Every value here is read from the sealed audit, IR and recommendation;
    nothing is computed by a model.
    """
    findings_by_id = {f["id"]: f for f in audit["findings"]}
    groups = [
        {
            "members": group["members"],
            "size": len(group["members"]),
            "finding_ids": group["finding_ids"],
            "evidence": [findings_by_id[fid]["evidence"] for fid in group["finding_ids"]],
        }
        for group in recommendations.get("consolidation_groups", [])
    ]
    contradictions = [
        {
            "finding_id": f["id"],
            "class": f["class"],
            "skill": f["skill"],
            "evidence": f["evidence"],
            "risk": CONTRADICTION_RISK[f["class"]],
        }
        for f in audit["findings"]
        if f["class"] in _CONTRADICTION_CLASSES
    ]
    texts = _rule_texts(ir)
    shared = []
    for f in audit["findings"]:
        if f["class"] != "STRUCTURAL_REDUNDANCY":
            continue
        text = texts.get((f["skill"], f["rule_id"]), "")
        holders = _skills_holding(ir, text)
        shared.append({
            "finding_id": f["id"],
            "text": text,
            "skill_count": len(holders),
            "skills": holders,
        })
    shared.sort(key=lambda item: (-item["skill_count"], item["text"]))
    return {
        "consolidation_groups": groups,
        "contradictions": contradictions,
        "shared_rule_texts": shared,
        "preconditions": audit.get("preconditions"),
    }


def build_final_report(
    corpus_root: str,
    confirm_executor: ConfirmExecutor,
    narration_executor: NarrationExecutor,
) -> dict[str, Any]:
    """Build and seal the final per-skill report for one corpus.

    ``corpus_root`` is compiled and audited fresh; it is never retained in
    the sealed result (only its skill count and digests are), consistent
    with the scan API's existing redaction policy (RT-03).
    """
    ir = compile_corpus(corpus_root)
    audit = audit_corpus(ir)
    confirmation = confirm_candidates(audit, ir, confirm_executor)
    all_skill_names = [skill["identity"]["name"] for skill in ir["skills"]]
    recommendations = compute_recommendations(audit, confirmation, all_skill_names)
    findings_by_id = {f["id"]: f for f in audit["findings"]}

    skills: dict[str, Any] = {}
    for skill_name, skill_recommendation in recommendations["skills"].items():
        narration = narrate_skill(skill_name, skill_recommendation, findings_by_id, narration_executor)
        skill_findings = [
            findings_by_id[fid]
            for fid in sorted(
                set(skill_recommendation["confirmed_finding_ids"])
                | set(skill_recommendation["rejected_finding_ids"])
                | set(skill_recommendation["pending_finding_ids"])
                | set(skill_recommendation["consolidation_finding_ids"])
            )
        ]
        skills[skill_name] = {
            "recommendation": skill_recommendation["recommendation"],
            "confirmed_finding_ids": skill_recommendation["confirmed_finding_ids"],
            "rejected_finding_ids": skill_recommendation["rejected_finding_ids"],
            "pending_finding_ids": skill_recommendation["pending_finding_ids"],
            "consolidation_group": skill_recommendation["consolidation_group"],
            "consolidation_finding_ids": skill_recommendation["consolidation_finding_ids"],
            "findings": skill_findings,
            "narrative": narration["narrative"],
            "narration_blocked": narration["blocked"],
            "narration_error": narration["error"],
            "cited_finding_ids": narration["cited_finding_ids"],
            "untraceable_finding_ids": narration["untraceable_finding_ids"],
        }

    by_recommendation: dict[str, int] = {}
    for skill in skills.values():
        by_recommendation[skill["recommendation"]] = by_recommendation.get(skill["recommendation"], 0) + 1

    report: dict[str, Any] = {
        "schema_version": FINAL_REPORT_VERSION,
        "skill_count": len(ir["skills"]),
        "audit_digest": audit["audit_digest"],
        "confirmation_digest": confirmation["confirmation_digest"],
        "recommendation_digest": recommendations["recommendation_digest"],
        "confirmation_digest_mismatch": recommendations["confirmation_digest_mismatch"],
        "summary": {
            "by_recommendation": by_recommendation,
            "total_skills": len(skills),
        },
        "corpus": _corpus_sections(ir, audit, recommendations),
        "skills": skills,
    }
    report["report_digest"] = digest_payload(report)
    return report

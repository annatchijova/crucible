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

FINAL_REPORT_VERSION = "crucible-final-report/v1"


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
    recommendations = compute_recommendations(audit, confirmation)
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
            )
        ]
        skills[skill_name] = {
            "recommendation": skill_recommendation["recommendation"],
            "confirmed_finding_ids": skill_recommendation["confirmed_finding_ids"],
            "rejected_finding_ids": skill_recommendation["rejected_finding_ids"],
            "pending_finding_ids": skill_recommendation["pending_finding_ids"],
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
        "skills": skills,
    }
    report["report_digest"] = digest_payload(report)
    return report

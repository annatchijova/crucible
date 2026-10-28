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

from pathlib import Path
from typing import Any

from .auditor import audit_corpus
from .compiler import ON_DUPLICATE_ERROR, compile_corpus
from .confirm import ConfirmExecutor, confirm_candidates
from .ir import digest_payload
from .narrator import NarrationExecutor, narrate_corpus, narrate_skill
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


def _read_corpus(corpus_root: str, ir: dict[str, Any]) -> dict[str, str]:
    """Each compiled skill's SKILL.md text, keyed by its name."""
    root = Path(corpus_root).resolve()
    return {
        skill["identity"]["name"]: (root / skill["identity"]["source_path"]).read_text(encoding="utf-8")
        for skill in ir["skills"]
    }


def _repair_section(
    corpus_root: str,
    ir: dict[str, Any],
    audit: dict[str, Any],
    skills: dict[str, Any],
    proposer: Any,
    limit: int,
) -> dict[str, Any]:
    """Suggest a gated rewrite for up to ``limit`` MODIFY skills.

    Skills are taken in order of most confirmed findings, then name, so the
    selection is deterministic and the count left out is stated.
    """
    from .repair_suggestions import NOT_REPAIRED_HERE, suggest_rewrite

    findings_by_id = {f["id"]: f for f in audit["findings"]}
    eligible = sorted(
        (
            name for name, skill in skills.items()
            if skill["recommendation"] == "MODIFY"
            and any(
                findings_by_id[fid]["class"] not in NOT_REPAIRED_HERE
                and findings_by_id[fid]["skill"] == name
                for fid in skill["confirmed_finding_ids"]
            )
        ),
        key=lambda name: (-len(skills[name]["confirmed_finding_ids"]), name),
    )
    corpus = _read_corpus(corpus_root, ir)
    attempted = eligible[:limit]
    for name in attempted:
        targets = [
            findings_by_id[fid] for fid in skills[name]["confirmed_finding_ids"]
            if findings_by_id[fid]["skill"] == name
        ]
        skills[name]["suggested_rewrite"] = suggest_rewrite(
            corpus, audit["findings"], name, targets, proposer
        )
    outcomes = [skills[name]["suggested_rewrite"]["outcome"] for name in attempted]
    return {
        "eligible": len(eligible),
        "attempted": len(attempted),
        "accepted": outcomes.count("ACCEPTED"),
        "not_attempted": eligible[limit:],
        "behavioral_gate": None,
    }


def _consolidation_section(
    corpus_root: str,
    ir: dict[str, Any],
    confirmation: dict[str, Any],
    proposer: Any,
) -> dict[str, Any]:
    """Run L16 over every duplicate group and keep what a reader needs.

    The model only proposes the merged text; whether it is acceptable is the
    deterministic gate's verdict, recorded per group with its reason.
    """
    from .consolidation import run_consolidation_batch

    corpus = _read_corpus(corpus_root, ir)
    batch = run_consolidation_batch(corpus=corpus, confirmation=confirmation, proposer=proposer)
    proposals = []
    for report in batch["reports"]:
        proposal = report.get("proposal") or {}
        proposals.append({
            "members": sorted(report["cluster"]),
            "outcome": report["outcome"],
            "rejection_reason": report["rejection_reason"],
            "proposer": proposal.get("proposer"),
            "proposed_name": proposal.get("proposed_name"),
            "proposed_text": proposal.get("proposed_text"),
            "coverage_gaps": report["coverage_gaps"],
            "new_findings": report["new_findings"],
            "consolidation_digest": report["consolidation_digest"],
        })
    return {
        "batch_digest": batch["batch_digest"],
        "behavioral_gate": None,
        "proposals": proposals,
    }


def build_final_report(
    corpus_root: str,
    confirm_executor: ConfirmExecutor,
    narration_executor: NarrationExecutor,
    *,
    on_duplicate_name: str = ON_DUPLICATE_ERROR,
    consolidation_proposer: Any = None,
    repair_proposer: Any = None,
    repair_limit: int = 10,
    input_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and seal the final per-skill report for one corpus.

    ``corpus_root`` is compiled and audited fresh; it is never retained in
    the sealed result (only its skill count and digests are), consistent
    with the scan API's existing redaction policy (RT-03).

    ``consolidation_proposer``, when given, runs L16 over every duplicate
    group and adds each proposed merge with the gate's verdict.
    ``repair_proposer``, when given, suggests a gated rewrite for up to
    ``repair_limit`` skills recommended MODIFY.
    ``input_scope`` describes what was scanned (a single skill, a directory,
    the installed skills and their coverage) so the report states it.
    """
    ir = compile_corpus(corpus_root, on_duplicate_name=on_duplicate_name)
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
        "input": {
            **(input_scope or {"scope": "directory"}),
            "excluded_duplicate_names": ir.get("excluded", []),
        },
        "corpus": _corpus_sections(ir, audit, recommendations),
        "skills": skills,
    }
    if consolidation_proposer is not None and recommendations["consolidation_groups"]:
        report["corpus"]["consolidation"] = _consolidation_section(
            corpus_root, ir, confirmation, consolidation_proposer
        )
    if repair_proposer is not None:
        report["corpus"]["repairs"] = _repair_section(
            corpus_root, ir, audit, skills, repair_proposer, repair_limit
        )
    report["executive_summary"] = narrate_corpus(report, narration_executor)
    report["report_digest"] = digest_payload(report)
    return report

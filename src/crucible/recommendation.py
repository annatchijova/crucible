"""L15 deterministic recommendation core.

Computes, per skill, one of four engineering recommendations from the L2
audit's findings and (when available) the L2.5/L12 confirmation layer's
verdicts. This module makes the recommendation. It never calls an LLM and
never reads provider credentials. The LLM narrator (narrator.py) only
phrases this module's output in prose; it must not change which bucket a
skill falls into, and any finding id it mentions must exist here so the
narration stays traceable to the sealed artifacts (TECHNICAL.md L15).

Recommendations:

- KEEP: no findings at all for this skill.
- NEEDS_CONFIRMATION: only CANDIDATE findings exist, none of them have a
  CONFIRMED verdict from the confirmation layer (either confirmation was
  never run, was blocked, returned UNCLEAR, or the finding's class has no
  registered confirmation prompt). Nothing here is dismissed as fixed;
  the honest answer is "run --confirm before deciding."
- DELETE: the skill has a CONFIRMED (natively, or via L2.5) redundancy
  finding (STRUCTURAL_REDUNDANCY or SEMANTIC_REDUNDANCY) -- the skill
  substantively duplicates another skill already in the corpus, so the
  engineering answer is "remove it," not "repair it."
- MODIFY: the skill has at least one other CONFIRMED finding. This is the
  default outcome for a real, non-redundant methodological defect.

A REJECTED confirmation verdict removes a candidate from consideration
entirely: the L2.5 layer judged it not to be a genuine instance of the
stated defect, so it contributes to no recommendation.

What this module deliberately does NOT do: assign a severity score, rank
findings by subjective importance, or recommend DELETE for a skill whose
only defect is, say, a missing timeout or an unbounded retry -- those are
repairable and get MODIFY. Extending DELETE to cover e.g. pervasive
METHODOLOGICAL_VACUITY (a skill with no checkable content at all) is a
real candidate for a later level; it is not implemented here because it
would require a second, independently-justified rule, not an extension of
the redundancy one.
"""

from __future__ import annotations

from typing import Any

from .ir import digest_payload

RECOMMENDATION_VERSION = "crucible-recommendation/v1"

_REDUNDANCY_CLASSES = frozenset({"STRUCTURAL_REDUNDANCY", "SEMANTIC_REDUNDANCY"})

_KEEP = "KEEP"
_NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
_DELETE = "DELETE"
_MODIFY = "MODIFY"


def compute_recommendations(
    audit: dict[str, Any],
    confirmation: dict[str, Any] | None = None,
    all_skill_names: list[str] | None = None,
) -> dict[str, Any]:
    """Compute one recommendation per skill.

    ``audit`` is a sealed ``crucible-audit/v1`` artifact. ``confirmation``,
    if given, is a sealed ``crucible-confirmation/v1`` artifact whose
    ``source_audit_digest`` should match ``audit["audit_digest"]`` --
    a mismatch is recorded, not silently ignored, since a recommendation
    computed against the wrong audit's confirmations would misattribute
    CONFIRMED/REJECTED verdicts to findings that never produced them.

    ``all_skill_names``, if given, is the full set of skill names in the
    compiled corpus (``ir["skills"][i]["identity"]["name"]`` for each
    skill). Without it, a skill with zero findings has no entry at all
    in the result -- not even KEEP -- because the only skill names this
    function can see are the ones mentioned in ``audit["findings"]``.
    That silently drops every clean skill from any report built on this
    function's output (confirmed: `build_final_report`'s rendered
    Markdown/HTML/PDF header states the true `skill_count` but the body
    lists nothing for a skill with no findings, a visible, misleading
    gap). Passing the full name list lets every skill with zero findings
    get an explicit KEEP entry instead of silent omission. Kept optional,
    defaulting to the old (buggy) behavior, since existing callers build
    a bare ``audit`` dict in tests without a real compiled corpus to draw
    names from.
    """
    findings = audit.get("findings", [])
    confirmation_by_id = _index_confirmations(confirmation)
    confirmation_digest_mismatch = (
        confirmation is not None
        and confirmation.get("source_audit_digest") != audit.get("audit_digest")
    )

    by_skill: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        skill = finding.get("skill") or "(corpus-level)"
        by_skill.setdefault(skill, []).append(finding)
    for skill_name in all_skill_names or ():
        by_skill.setdefault(skill_name, [])

    skills: dict[str, Any] = {}
    for skill_name, skill_findings in sorted(by_skill.items()):
        skills[skill_name] = _recommend_for_skill(
            skill_findings, confirmation_by_id, confirmation_digest_mismatch
        )

    result: dict[str, Any] = {
        "schema_version": RECOMMENDATION_VERSION,
        "source_audit_digest": audit.get("audit_digest"),
        "source_confirmation_digest": (
            confirmation.get("confirmation_digest") if confirmation else None
        ),
        "confirmation_digest_mismatch": confirmation_digest_mismatch,
        "skills": skills,
    }
    result["recommendation_digest"] = digest_payload(result)
    return result


def _index_confirmations(
    confirmation: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if confirmation is None:
        return {}
    return {
        entry["finding_id"]: entry
        for entry in confirmation.get("confirmations", [])
        if "finding_id" in entry
    }


def _finding_is_confirmed(
    finding: dict[str, Any],
    confirmation_by_id: dict[str, dict[str, Any]],
) -> bool:
    if finding.get("epistemic_status") == "CONFIRMED":
        return True
    entry = confirmation_by_id.get(finding.get("id"))
    return entry is not None and entry.get("verdict") == "CONFIRMED"


def _finding_is_rejected(
    finding: dict[str, Any],
    confirmation_by_id: dict[str, dict[str, Any]],
) -> bool:
    entry = confirmation_by_id.get(finding.get("id"))
    return entry is not None and entry.get("verdict") == "REJECTED"


def _recommend_for_skill(
    findings: list[dict[str, Any]],
    confirmation_by_id: dict[str, dict[str, Any]],
    confirmation_digest_mismatch: bool,
) -> dict[str, Any]:
    confirmed_basis: list[str] = []
    confirmed_classes: set[str] = set()
    rejected_ids: list[str] = []
    pending_ids: list[str] = []

    for finding in findings:
        finding_id = finding.get("id", "")
        if confirmation_digest_mismatch:
            # Do not trust any verdict computed against a different audit.
            if finding.get("epistemic_status") == "CONFIRMED":
                confirmed_basis.append(finding_id)
                confirmed_classes.add(finding.get("class", ""))
            else:
                pending_ids.append(finding_id)
            continue
        if _finding_is_confirmed(finding, confirmation_by_id):
            confirmed_basis.append(finding_id)
            confirmed_classes.add(finding.get("class", ""))
        elif _finding_is_rejected(finding, confirmation_by_id):
            rejected_ids.append(finding_id)
        else:
            pending_ids.append(finding_id)

    if confirmed_classes & _REDUNDANCY_CLASSES:
        recommendation = _DELETE
    elif confirmed_basis:
        recommendation = _MODIFY
    elif pending_ids:
        recommendation = _NEEDS_CONFIRMATION
    else:
        recommendation = _KEEP

    return {
        "recommendation": recommendation,
        "confirmed_finding_ids": sorted(confirmed_basis),
        "rejected_finding_ids": sorted(rejected_ids),
        "pending_finding_ids": sorted(pending_ids),
        "total_finding_count": len(findings),
    }

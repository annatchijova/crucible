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
- CONSOLIDATE: the skill belongs to a group of skills joined by CONFIRMED
  SEMANTIC_REDUNDANCY pairs (a connected component, so a chain of ten
  near-copies is one group of ten). Every member gets CONSOLIDATE and the
  same ``consolidation_group``: the engineering answer is "merge these into
  one," and which member survives is a decision for the merge, not for this
  module. The L16 consolidation gate (consolidation.py) is the path that
  proposes and checks that merge.
- MODIFY: the skill has at least one other CONFIRMED finding. This is the
  default outcome for a real, non-redundant methodological defect.

A REJECTED confirmation verdict removes a candidate from consideration
entirely: the L2.5 layer judged it not to be a genuine instance of the
stated defect, so it contributes to no recommendation.

v1 recommended DELETE for the skill a redundancy finding happened to be
attributed to, which the auditor picks by name order: of two identical
skills ``a`` and ``b``, ``a`` was marked DELETE and ``b`` KEEP. That turned
alphabetical order into an engineering recommendation, and a group larger
than a pair was never reported as a group. v2 replaces DELETE with
CONSOLIDATE, applied to the whole group.

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

import re
from typing import Any

from .confirm import _parse_semantic_redundancy_pair
from .graph import _find_components
from .ir import digest_payload

RECOMMENDATION_VERSION = "crucible-recommendation/v2"

_KEEP = "KEEP"
_NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
_CONSOLIDATE = "CONSOLIDATE"
_MODIFY = "MODIFY"

RECOMMENDATIONS = (_CONSOLIDATE, _MODIFY, _NEEDS_CONFIRMATION, _KEEP)

_CONTRADICTION_CLASSES = frozenset({"NORMATIVE_CONFLICT", "CONDITIONAL_CONTRADICTION"})

# COUPLING: auditor.py's _check_normative_conflict and
# _check_conditional_contradiction word their evidence as
# "... <MODALITY> in <skill> vs <MODALITY> in <skill> (rule <id>)".
# Changing that wording there and this pattern here must happen together.
_CONTRADICTION_PARTIES_RE = re.compile(r" in (\S+) vs \S+ in (\S+) \(rule [^)]*\)$")


def contradiction_parties(finding: dict[str, Any]) -> list[str]:
    """Both skills named by a contradiction finding, or just its attributed
    skill when the evidence cannot be parsed.

    A contradiction is attributed to one of its two skills, but it is a
    property of the pair: without this, the other skill read KEEP with "no
    findings" while it held half of a conflict.
    """
    match = _CONTRADICTION_PARTIES_RE.search(finding.get("evidence", ""))
    if match is None:
        return [finding.get("skill") or "(corpus-level)"]
    return sorted(set(match.groups()))


def compute_recommendations(
    audit: dict[str, Any],
    confirmation: dict[str, Any] | None = None,
    all_skill_names: list[str] | None = None,
) -> dict[str, Any]:
    """Compute one recommendation per skill.

    ``audit`` is a sealed ``crucible-audit/v2`` artifact. ``confirmation``,
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
        if finding.get("class") in _CONTRADICTION_CLASSES:
            for party in contradiction_parties(finding):
                if party != skill:
                    by_skill.setdefault(party, []).append(finding)
    for skill_name in all_skill_names or ():
        by_skill.setdefault(skill_name, [])

    groups = consolidation_groups(
        findings, confirmation_by_id, confirmation_digest_mismatch
    )
    group_by_member = {
        member: group for group in groups for member in group["members"]
    }
    for member in group_by_member:
        by_skill.setdefault(member, [])

    skills: dict[str, Any] = {}
    for skill_name, skill_findings in sorted(by_skill.items()):
        skills[skill_name] = _recommend_for_skill(
            skill_findings, confirmation_by_id, confirmation_digest_mismatch,
            group_by_member.get(skill_name),
        )

    result: dict[str, Any] = {
        "schema_version": RECOMMENDATION_VERSION,
        "source_audit_digest": audit.get("audit_digest"),
        "source_confirmation_digest": (
            confirmation.get("confirmation_digest") if confirmation else None
        ),
        "confirmation_digest_mismatch": confirmation_digest_mismatch,
        "consolidation_groups": groups,
        "skills": skills,
    }
    result["recommendation_digest"] = digest_payload(result)
    return result


def consolidation_groups(
    findings: list[dict[str, Any]],
    confirmation_by_id: dict[str, dict[str, Any]],
    confirmation_digest_mismatch: bool = False,
) -> list[dict[str, Any]]:
    """Connected components of CONFIRMED SEMANTIC_REDUNDANCY pairs.

    Each group carries its sorted members and the ids of the pair findings
    that join it, so every member can cite the evidence for its grouping
    even though each pair finding is attributed to only one of its skills.
    Verdicts from a confirmation computed against another audit are not
    trusted, and SEMANTIC_REDUNDANCY is never natively CONFIRMED, so a
    mismatch yields no groups.
    """
    edges: list[dict[str, Any]] = []
    names: set[str] = set()
    pair_findings: list[tuple[str, str, str]] = []
    for finding in findings:
        if finding.get("class") != "SEMANTIC_REDUNDANCY":
            continue
        if confirmation_digest_mismatch:
            continue
        if not _finding_is_confirmed(finding, confirmation_by_id):
            continue
        pair = _parse_semantic_redundancy_pair(finding)
        if pair is None:
            continue
        skill_a, skill_b, _ratio = pair
        edges.append({"source": skill_a, "target": skill_b, "resolved": True})
        names.update((skill_a, skill_b))
        pair_findings.append((skill_a, skill_b, finding.get("id", "")))

    groups = []
    for members in _find_components(edges, names):
        member_set = set(members)
        groups.append({
            "members": sorted(members),
            "finding_ids": sorted(
                fid for a, b, fid in pair_findings if a in member_set
            ),
        })
    return sorted(groups, key=lambda group: group["members"])


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
    group: dict[str, Any] | None = None,
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

    if group is not None:
        recommendation = _CONSOLIDATE
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
        "consolidation_group": group["members"] if group else [],
        "consolidation_finding_ids": group["finding_ids"] if group else [],
    }

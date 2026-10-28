"""Suggested rewrites for the narrated report (L15 + L6).

For a skill the report recommends to MODIFY, a proposer rewrites the skill to
address its confirmed findings, and Crucible decides deterministically whether
the rewrite is acceptable: every targeted finding class must be gone from that
skill, and no (class, skill) pair may appear that the original audit did not
have. The proposer is the same pluggable L6 proposer as bob.py -- the rule-based
one or Nemotron -- applied once per targeted class on the evolving text, so no
new prompt is introduced here.

The gate reads text only. An accepted rewrite is one the auditor no longer
objects to; it is not evidence that an agent following it behaves better.
That is the risk named at the start of the project (a repair can silence the
detector without fixing the behaviour), and every suggestion says so.
"""

from __future__ import annotations

import difflib
from typing import Any

from .bob import Proposer, _compile_and_audit
from .ir import digest_payload

REPAIR_SUGGESTION_VERSION = "crucible-repair-suggestion/v1"

# Classes that are not one skill's to repair: redundancy is resolved by
# consolidation, and a contradiction belongs to two skills at once.
NOT_REPAIRED_HERE = frozenset({
    "SEMANTIC_REDUNDANCY",
    "STRUCTURAL_REDUNDANCY",
    "NORMATIVE_CONFLICT",
    "CONDITIONAL_CONTRADICTION",
})

OUTCOME_ACCEPTED = "ACCEPTED"
OUTCOME_REJECTED = "REJECTED"
OUTCOME_NO_PROPOSAL = "NO_PROPOSAL"
OUTCOME_BLOCKED = "BLOCKED"

LIMITATION = (
    "The gate re-audits text only: an accepted rewrite is one the auditor no "
    "longer objects to, not evidence that an agent following it behaves better."
)


def _diff(before: str, after: str, name: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"{name}/SKILL.md (current)",
        tofile=f"{name}/SKILL.md (suggested)",
        n=2,
    ))


def suggest_rewrite(
    corpus: dict[str, str],
    original_findings: list[dict[str, Any]],
    skill_name: str,
    target_findings: list[dict[str, Any]],
    proposer: Proposer,
) -> dict[str, Any]:
    """Propose one rewrite of ``skill_name`` and gate it.

    ``corpus`` maps every skill name to its SKILL.md text and must be the
    corpus ``original_findings`` was audited from.
    """
    targets = [f for f in target_findings if f.get("class") not in NOT_REPAIRED_HERE]
    target_classes = sorted({f["class"] for f in targets})
    result: dict[str, Any] = {
        "schema_version": REPAIR_SUGGESTION_VERSION,
        "skill": skill_name,
        "target_finding_ids": sorted(f["id"] for f in targets),
        "target_classes": target_classes,
        "proposals": [],
        "outcome": OUTCOME_NO_PROPOSAL,
        "rejection_reason": None,
        "resolved_classes": [],
        "persisting_classes": [],
        "new_findings": [],
        "diff": None,
        "proposed_text": None,
        "behavioral_gate": None,
        "limitation": LIMITATION,
    }
    original_text = corpus[skill_name]
    text = original_text
    seen_classes: set[str] = set()
    for finding in sorted(targets, key=lambda f: f["id"]):
        if finding["class"] in seen_classes:
            continue
        seen_classes.add(finding["class"])
        try:
            proposal = proposer.propose(finding, text, {"skill": skill_name})
        except Exception as exc:  # a proposer failure is recorded, not raised
            proposal = {"proposed_text": None, "rationale": str(exc), "proposer": "unknown"}
        result["proposals"].append({
            "finding_id": finding["id"],
            "class": finding["class"],
            "proposer": proposal.get("proposer", "unknown"),
            "rationale": proposal.get("rationale", ""),
            "applied": proposal.get("proposed_text") is not None,
        })
        if proposal.get("blocked"):
            result["outcome"] = OUTCOME_BLOCKED
            result["rejection_reason"] = proposal.get("rationale")
            result["suggestion_digest"] = digest_payload(result)
            return result
        if proposal.get("proposed_text") is not None:
            text = proposal["proposed_text"]

    if text == original_text:
        result["suggestion_digest"] = digest_payload(result)
        return result

    repaired = dict(corpus)
    repaired[skill_name] = text
    result["proposed_text"] = text
    result["diff"] = _diff(original_text, text, skill_name)
    try:
        repaired_findings = _compile_and_audit(repaired)["findings"]
    except ValueError as exc:
        result["outcome"] = OUTCOME_REJECTED
        result["rejection_reason"] = f"COMPILE_ERROR: {exc}"
        result["suggestion_digest"] = digest_payload(result)
        return result

    remaining = {f["class"] for f in repaired_findings if f.get("skill") == skill_name}
    result["resolved_classes"] = [c for c in target_classes if c not in remaining]
    result["persisting_classes"] = [c for c in target_classes if c in remaining]
    original_pairs = {(f.get("class"), f.get("skill")) for f in original_findings}
    result["new_findings"] = sorted({
        f"{f['class']} on {f['skill']}"
        for f in repaired_findings
        if (f.get("class"), f.get("skill")) not in original_pairs
    })
    if result["persisting_classes"]:
        result["outcome"] = OUTCOME_REJECTED
        result["rejection_reason"] = "FINDING_PERSISTS"
    elif result["new_findings"]:
        result["outcome"] = OUTCOME_REJECTED
        result["rejection_reason"] = "NEW_FINDINGS"
    else:
        result["outcome"] = OUTCOME_ACCEPTED
    result["suggestion_digest"] = digest_payload(result)
    return result

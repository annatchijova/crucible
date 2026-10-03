"""Human-readable terminal rendering of crucible's JSON reports.

Stdlib only -- no new dependency (no rich/textual). ``--human`` on the
CLI renders the SAME report dict the JSON path would print, just as a
scannable terminal summary instead of raw JSON: this module never
computes anything the sealed report did not already contain, and the
underlying JSON path is unchanged and still available for machine
consumption or piping.

The report shape is detected by a few distinctive top-level keys (e.g.
``audit_digest`` + ``findings`` for an L2 audit artifact,
``mutation_digest`` for an L4 mutation report). Any shape not explicitly
recognized falls back to pretty-printed JSON, so ``--human`` is never a
downgrade -- worst case it looks exactly like today.

Color is ANSI escape codes, enabled only when stdout is a real terminal
(``sys.stdout.isatty()``); piped or redirected output is always plain
text, so this never corrupts a file or a pipe to another tool.
"""

from __future__ import annotations

import json
import sys
from typing import Any

_RESET = "\x1b[0m"
_CODES = {
    "bold": "1", "dim": "2", "red": "31", "green": "32",
    "yellow": "33", "blue": "34", "magenta": "35", "cyan": "36",
}


class _Colorizer:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def __call__(self, style: str, text: str) -> str:
        if not self.enabled:
            return text
        code = _CODES.get(style, "")
        return f"\x1b[{code}m{text}{_RESET}" if code else text


def _terminal_supports_color() -> bool:
    try:
        return sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


_STATUS_STYLE = {
    "CONFIRMED": "red", "CANDIDATE": "yellow", "OBSERVATION": "cyan",
    "PASS": "green", "FAIL": "red", "ABSTAINED": "dim",
    "ACCEPTED": "green", "REJECTED": "red", "BLOCKED": "yellow", "ERROR": "red",
    "KILLED": "green", "SURVIVED": "red",
    "COMPLETED": "green",
}


def _styled_status(c: _Colorizer, status: str) -> str:
    return c(_STATUS_STYLE.get(status, "bold"), status)


def _json_fallback(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def format_human(report: Any) -> str:
    """Render a crucible JSON report as a scannable terminal summary."""
    if not isinstance(report, dict):
        return _json_fallback(report) if isinstance(report, (list,)) else str(report)

    c = _Colorizer(_terminal_supports_color())

    if "audit_digest" in report and "findings" in report:
        return _format_audit(report, c)
    if "mutation_digest" in report:
        return _format_mutation(report, c)
    if "behavioral_digest" in report:
        return _format_behavioral(report, c)
    if "graph_digest" in report:
        return _format_graph(report, c)
    if "confirmation_digest" in report:
        return _format_confirmation(report, c)
    if "batch_digest" in report:
        return _format_consolidation_batch(report, c)
    if "outcome" in report and "rejection_reason" in report:
        return _format_outcome_report(report, c)

    return _json_fallback(report)


def _format_audit(report: dict[str, Any], c: _Colorizer) -> str:
    findings = report.get("findings", [])
    lines = [c("bold", f"Audit — {len(findings)} finding(s)")]
    for f in findings:
        lines.append(
            f"  [{_styled_status(c, f.get('epistemic_status', ''))}] "
            f"{c('bold', f.get('class', ''))} — {f.get('skill', '(corpus)')}"
        )
        lines.append(f"      {f.get('evidence', '')}")
    limitations = report.get("limitations", [])
    if limitations:
        lines.append(c("dim", f"  {len(limitations)} check(s) abstained (see limitations)"))
    lines.append(c("dim", f"  digest: {report.get('audit_digest', '')}"))
    return "\n".join(lines)


def _format_mutation(report: dict[str, Any], c: _Colorizer) -> str:
    summary = report.get("summary", {})
    lines = [
        c("bold", f"Mutation lab — kill rate {summary.get('kill_rate', '?')}"),
    ]
    for r in report.get("results", []):
        status = r.get("status", "")
        line = f"  [{_styled_status(c, status)}] {r.get('mutation_id', '')}"
        survivor = r.get("survivor_classification")
        if survivor:
            line += f" ({survivor})"
        lines.append(line)
    return "\n".join(lines)


def _format_behavioral(report: dict[str, Any], c: _Colorizer) -> str:
    lines = [c("bold", "Behavioral differential")]
    if report.get("nebius_blocked"):
        lines.append(c("yellow", f"  BLOCKED: {report.get('block_reason', '')}"))
    for run in report.get("runs", []) or report.get("local_fallback_runs", []):
        lines.append(
            f"  {c('bold', run.get('variant_id', ''))} "
            f"[{_styled_status(c, run.get('status', ''))}]"
        )
        for obs in run.get("observations", []):
            lines.append(
                f"      {obs.get('property_id', '')}: "
                f"{_styled_status(c, obs.get('status', ''))} — {obs.get('evidence', '')}"
            )
    return "\n".join(lines)


def _format_graph(report: dict[str, Any], c: _Colorizer) -> str:
    edges = report.get("edges", [])
    nodes = report.get("nodes", [])
    props = report.get("graph_properties", [])
    lines = [
        c("bold", f"Composition graph — {len(nodes)} node(s), {len(edges)} edge(s)"),
    ]
    for e in edges:
        arrow = "<->" if e.get("symmetric") else "->"
        resolved = "" if e.get("resolved") else c("red", " (unresolved)")
        lines.append(
            f"  {e.get('source', '')} {arrow} {e.get('target', '')} "
            f"[{e.get('edge_type', '')}]{resolved}"
        )
    for p in props:
        lines.append(
            f"  {c('yellow', p.get('property', ''))} ({p.get('skill', '')}): "
            f"{p.get('evidence', '')}"
        )
    return "\n".join(lines)


def _format_confirmation(report: dict[str, Any], c: _Colorizer) -> str:
    summary = report.get("summary", {})
    lines = [
        c("bold", f"Confirmation — {summary.get('confirmed', 0)} confirmed, "
          f"{summary.get('rejected', 0)} rejected, {summary.get('unclear', 0)} unclear"),
    ]
    if report.get("status") == "BLOCKED":
        lines.append(c("yellow", "  executor BLOCKED (no provider credential)"))
    for entry in report.get("confirmations", []):
        lines.append(
            f"  [{_styled_status(c, entry.get('verdict', ''))}] "
            f"{entry.get('finding_class', '')} ({entry.get('finding_id', '')})"
        )
        if entry.get("rationale"):
            lines.append(f"      {entry['rationale']}")
    return "\n".join(lines)


def _format_outcome_report(report: dict[str, Any], c: _Colorizer) -> str:
    """Shared renderer for bob/repair_loop/consolidation single-cluster
    reports -- they all carry {outcome, rejection_reason, proposal}."""
    outcome = report.get("outcome", "")
    lines = [c("bold", f"Outcome: {_styled_status(c, outcome)}")]
    reason = report.get("rejection_reason")
    if reason:
        lines.append(f"  reason: {c('red', str(reason))}")
    cluster = report.get("cluster")
    if cluster:
        lines.append(f"  cluster: {', '.join(cluster)}")
    finding = report.get("finding")
    if finding:
        lines.append(f"  targeted finding: {finding.get('class', '')} on {finding.get('skill', '')}")
    proposal = report.get("proposal")
    if proposal:
        name = proposal.get("proposed_name") or proposal.get("proposer", "")
        lines.append(f"  proposal: {name} — {proposal.get('rationale', '')}")
    for key in ("coverage_gaps", "new_findings", "external_references", "rewritten_external_references"):
        value = report.get(key)
        if value:
            lines.append(f"  {key}: {len(value)} item(s)")
    return "\n".join(lines)


def _format_consolidation_batch(report: dict[str, Any], c: _Colorizer) -> str:
    lines = [
        c("bold", f"Consolidation batch — {report.get('batch_status', '')} "
          f"({report.get('total_clusters', 0)} cluster(s): "
          f"{report.get('accepted_count', 0)} accepted, "
          f"{report.get('rejected_count', 0)} rejected, "
          f"{report.get('blocked_count', 0)} blocked)"),
    ]
    for r in report.get("reports", []):
        lines.append(f"  cluster {r.get('cluster', [])}: {_styled_status(c, r.get('outcome', ''))}")
    final_names = report.get("final_skill_names")
    if final_names:
        lines.append(f"  final corpus: {', '.join(final_names)}")
    return "\n".join(lines)

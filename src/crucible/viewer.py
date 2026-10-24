"""Read-only HTML viewer for sealed artifacts (L8).

The viewer reads a JSON artifact (any level or composite report) and
produces a self-contained HTML page that renders it. The viewer does
NOT compute anything: it does not re-run audits, re-compute digests, or
make decisions. It is a pure projection of the sealed artifact.

The HTML is self-contained: inline CSS, no external dependencies, no
JavaScript that computes anything. It is read-only.
"""

from __future__ import annotations

import html
import json
from typing import Any


def render_artifact_html(artifact: dict[str, Any]) -> str:
    """Render a sealed artifact as a self-contained HTML page.

    The artifact can be any level output (L1-L7) or a composite report.
    The viewer inspects the artifact's version field to determine the
    rendering strategy. It does NOT re-compute anything.
    """
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Crucible Artifact Viewer</title>",
        "<style>",
        _CSS,
        "</style>",
        "</head>",
        "<body>",
        '<div class="container">',
    ]

    # Determine artifact type from version field.
    version = (
        artifact.get("report_version")
        or artifact.get("loop_version")
        or artifact.get("bob_version")
        or artifact.get("behavioral_version")
        or artifact.get("mutation_version")
        or artifact.get("graph_version")
        or artifact.get("audit_version")
        or artifact.get("schema_version")
        or "unknown"
    )

    parts.append(f'<h1>Crucible Artifact</h1>')
    parts.append(f'<p class="version">Version: <code>{html.escape(version)}</code></p>')

    # Render the digest if present.
    for digest_key in (
        "report_digest",
        "loop_digest",
        "behavioral_digest",
        "mutation_digest",
        "graph_digest",
        "audit_digest",
        "artifact_digest",
    ):
        if digest_key in artifact:
            parts.append(
                f'<p class="digest">{html.escape(digest_key)}: '
                f'<code>{html.escape(str(artifact[digest_key]))}</code></p>'
            )
            break

    # Render Nebius blocked status if present.
    if "nebius_blocked" in artifact:
        blocked = artifact["nebius_blocked"]
        cls = "blocked" if blocked else "available"
        parts.append(f'<p class="status {cls}">Nebius: {"BLOCKED" if blocked else "AVAILABLE"}</p>')
        if artifact.get("block_reason"):
            parts.append(
                f'<p class="status-detail">{html.escape(str(artifact["block_reason"]))}</p>'
            )

    # Render composite report.
    if "levels" in artifact:
        parts.extend(_render_levels(artifact["levels"]))

    # Render findings if present.
    if "findings" in artifact and isinstance(artifact["findings"], list):
        parts.extend(_render_findings(artifact["findings"]))

    # Render mutation results if present.
    if "results" in artifact and isinstance(artifact["results"], list):
        parts.extend(_render_mutation_results(artifact["results"]))

    # Render behavioral runs if present.
    if "runs" in artifact and isinstance(artifact["runs"], list):
        parts.extend(_render_behavioral_runs(artifact["runs"]))

    # Render behavioral replay if present.
    if "behavioral_replay" in artifact and artifact["behavioral_replay"]:
        parts.extend(_render_behavioral_replay(artifact["behavioral_replay"]))

    # Render outcome if present.
    if "outcome" in artifact:
        outcome = artifact["outcome"]
        cls = "accepted" if outcome == "ACCEPTED" else "rejected"
        parts.append(
            f'<p class="outcome {cls}">Outcome: <strong>{html.escape(str(outcome))}</strong></p>'
        )
        if artifact.get("rejection_reason"):
            parts.append(
                f'<p class="rejection">Reason: {html.escape(str(artifact["rejection_reason"]))}</p>'
            )

    # Render summary if present.
    if "summary" in artifact:
        parts.extend(_render_summary(artifact["summary"]))

    # Scan coverage, duplicate-name exclusions, and per-check preconditions all
    # answer "what was NOT looked at", so they precede the static design limits.
    if isinstance(artifact.get("coverage"), dict):
        parts.extend(_render_coverage(artifact["coverage"]))

    if isinstance(artifact.get("excluded"), list):
        parts.extend(_render_excluded(artifact["excluded"]))

    if isinstance(artifact.get("preconditions"), dict):
        parts.extend(_render_preconditions(artifact["preconditions"]))

    # Render limitations if present.
    if "limitations" in artifact and isinstance(artifact["limitations"], list):
        parts.extend(_render_limitations(artifact["limitations"]))

    # Render chain of custody digests.
    parts.extend(_render_chain_of_custody(artifact))

    parts.append("</div>")
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts)


def _render_levels(levels: dict[str, Any]) -> list[str]:
    parts = ['<h2>Levels</h2>']
    for level_id in sorted(levels):
        level = levels[level_id]
        parts.append(f'<div class="level">')
        parts.append(f'<h3>{html.escape(level_id)}</h3>')
        parts.append('<table>')
        for key in sorted(level):
            value = level[key]
            parts.append(
                f'<tr><td class="key">{html.escape(key)}</td>'
                f'<td>{_render_value(value)}</td></tr>'
            )
        parts.append('</table>')
        parts.append('</div>')
    return parts


def _render_findings(findings: list[dict[str, Any]]) -> list[str]:
    parts = ['<h2>Findings</h2>']
    if not findings:
        parts.append('<p class="empty">No findings.</p>')
        return parts
    parts.append('<table class="findings">')
    parts.append('<tr><th>ID</th><th>Class</th><th>Skill</th><th>Status</th><th>Evidence</th></tr>')
    for f in findings:
        parts.append(
            f'<tr><td>{html.escape(str(f.get("id", "")))}</td>'
            f'<td>{html.escape(str(f.get("class", "")))}</td>'
            f'<td>{html.escape(str(f.get("skill", "")))}</td>'
            f'<td>{html.escape(str(f.get("epistemic_status", "")))}</td>'
            f'<td>{html.escape(str(f.get("evidence", "")))}</td></tr>'
        )
    parts.append('</table>')
    return parts


def _render_mutation_results(results: list[dict[str, Any]]) -> list[str]:
    parts = ['<h2>Mutation Results</h2>']
    parts.append('<table class="mutations">')
    parts.append('<tr><th>ID</th><th>Class</th><th>Status</th><th>Survivor</th><th>Evidence</th></tr>')
    for r in results:
        sc = r.get("survivor_classification") or ""
        parts.append(
            f'<tr><td>{html.escape(str(r.get("mutation_id", "")))}</td>'
            f'<td>{html.escape(str(r.get("mutation_class", "")))}</td>'
            f'<td class="status-{html.escape(str(r.get("status", "")).lower())}">'
            f'{html.escape(str(r.get("status", "")))}</td>'
            f'<td>{html.escape(str(sc))}</td>'
            f'<td>{html.escape(str(r.get("evidence", "")))}</td></tr>'
        )
    parts.append('</table>')
    return parts


def _render_behavioral_runs(runs: list[dict[str, Any]]) -> list[str]:
    parts = ['<h2>Behavioral Differential</h2>']
    parts.append('<table class="behavioral">')
    parts.append('<tr><th>Variant</th><th>Status</th><th>Properties</th></tr>')
    for r in runs:
        observations = r.get("observations", [])
        props = ", ".join(
            f'<span title="{html.escape(str(o.get("evidence", "")))}">'
            f'{html.escape(str(o.get("property_id", "")))}='
            f'{html.escape(str(o.get("status", "")))}</span>'
            for o in observations
        )
        parts.append(
            f'<tr><td>{html.escape(str(r.get("variant_id", "")))}</td>'
            f'<td>{html.escape(str(r.get("status", "")))}</td>'
            f'<td>{props}</td></tr>'
        )
    parts.append('</table>')
    return parts


def _render_behavioral_replay(replay: dict[str, Any]) -> list[str]:
    parts = ['<h2>Behavioral Replay</h2>']
    regression = replay.get("regression", False)
    cls = "regression-yes" if regression else "regression-no"
    parts.append(
        f'<p class="{cls}">Regression: <strong>{regression}</strong></p>'
    )
    regressions = replay.get("regressions", [])
    if regressions:
        parts.append('<table class="regressions">')
        parts.append('<tr><th>Property</th><th>Original</th><th>Repaired</th></tr>')
        for reg in regressions:
            parts.append(
                f'<tr><td>{html.escape(str(reg.get("property_id", "")))}</td>'
                f'<td>{html.escape(str(reg.get("original_status", "")))}</td>'
                f'<td>{html.escape(str(reg.get("repaired_status", "")))}</td></tr>'
            )
        parts.append('</table>')
    return parts


def _render_summary(summary: dict[str, Any]) -> list[str]:
    parts = ['<h2>Summary</h2>']
    parts.append('<table>')
    for key in sorted(summary):
        parts.append(
            f'<tr><td class="key">{html.escape(key)}</td>'
            f'<td>{_render_value(summary[key])}</td></tr>'
        )
    parts.append('</table>')
    return parts


def _render_limitations(limitations: list[dict[str, Any]]) -> list[str]:
    """Permanent design scope, identical for every corpus.

    These are NOT abstentions. An abstention is corpus-dependent and is
    reported by _render_preconditions; labelling a static list "abstentions"
    told every reader of every corpus that checks had abstained.
    """
    if not limitations:
        return []
    parts = ['<h2>Documented design limitations</h2>',
             '<p class="note">Permanent scope of the analyzer, the same for '
             'every corpus. Not a statement about this run.</p>']
    parts.append('<ul class="limitations">')
    for lim in limitations:
        parts.append(
            f'<li><strong>{html.escape(str(lim.get("check_class", "")))}</strong>: '
            f'{html.escape(str(lim.get("reason", "")))}</li>'
        )
    parts.append('</ul>')
    return parts


def _render_preconditions(preconditions: dict[str, Any]) -> list[str]:
    """Per-check: did this corpus supply the input the check consumes?

    A check that found nothing because its input was absent is not evidence
    that the corpus is clean, which is the distinction this block exists to
    make visible (ADR-0025).
    """
    checks = preconditions.get("checks")
    if not isinstance(checks, list) or not checks:
        return []
    abstained = [c for c in checks if c.get("outcome") == "ABSTAINED"]
    parts = [f'<h2>Check preconditions &mdash; {len(abstained)} abstained on this corpus</h2>']
    if preconditions.get("limitation"):
        parts.append(
            f'<p class="note">{html.escape(str(preconditions["limitation"]))}</p>'
        )
    parts.append('<table class="preconditions">')
    parts.append('<tr><th>Check</th><th>Outcome</th><th>Requires</th>'
                 '<th>Observed</th><th>Why it abstained</th></tr>')
    for check in sorted(checks, key=lambda c: (c.get("outcome") != "ABSTAINED",
                                               str(c.get("check_class", "")))):
        outcome = str(check.get("outcome", ""))
        css = "outcome-abstained" if outcome == "ABSTAINED" else "outcome-exercised"
        parts.append(
            f'<tr><td>{html.escape(str(check.get("check_class", "")))}</td>'
            f'<td class="{css}">{html.escape(outcome)}</td>'
            f'<td><code>{html.escape(str(check.get("requires", "")))}</code></td>'
            f'<td class="int">{html.escape(str(check.get("observed", "")))}</td>'
            f'<td>{html.escape(str(check.get("reason") or ""))}</td></tr>'
        )
    parts.append('</table>')
    inputs = preconditions.get("corpus_inputs")
    if isinstance(inputs, dict) and inputs:
        parts.append('<h3>Corpus inputs these outcomes were computed from</h3>')
        parts.append('<table class="corpus-inputs">')
        for key in sorted(inputs):
            parts.append(
                f'<tr><td class="key">{html.escape(key)}</td>'
                f'<td class="int">{html.escape(str(inputs[key]))}</td></tr>'
            )
        parts.append('</table>')
    return parts


def _render_excluded(excluded: list[dict[str, Any]]) -> list[str]:
    """Skills the compiler dropped, and whether dropping them lost content.

    Always rendered, including when empty: an artifact that silently omits
    this cannot be told apart from one that excluded something (ADR-0026).
    """
    parts = [f'<h2>Excluded skills &mdash; {len(excluded)}</h2>']
    if not excluded:
        parts.append('<p class="empty">None. Every discovered skill was analyzed.</p>')
        return parts
    lost = sum(1 for e in excluded
               if e.get("reason") == "DUPLICATE_NAME_DISTINCT_CONTENT")
    parts.append(
        f'<p class="note">{lost} of {len(excluded)} dropped a distinct '
        f'methodology that shares a name with one that was kept; the rest were '
        f'byte-identical republications, where nothing analysable was lost.</p>'
    )
    parts.append('<table class="excluded">')
    parts.append('<tr><th>Name</th><th>Dropped path</th><th>Kept path</th>'
                 '<th>Reason</th></tr>')
    for entry in excluded:
        reason = str(entry.get("reason", ""))
        css = ("regression-yes" if reason == "DUPLICATE_NAME_DISTINCT_CONTENT"
               else "status-abstained")
        parts.append(
            f'<tr><td>{html.escape(str(entry.get("name", "")))}</td>'
            f'<td><code>{html.escape(str(entry.get("source_path", "")))}</code></td>'
            f'<td><code>{html.escape(str(entry.get("kept_source_path", "")))}</code></td>'
            f'<td class="{css}">{html.escape(reason)}</td></tr>'
        )
    parts.append('</table>')
    return parts


def _render_coverage(coverage: dict[str, Any]) -> list[str]:
    """What the scan found versus what it analyzed."""
    status = str(coverage.get("status", ""))
    css = "regression-no" if status == "COMPLETE" else "status-survived"
    parts = [f'<h2>Scan coverage &mdash; <span class="{css}">{html.escape(status)}</span></h2>']
    if coverage.get("scope"):
        parts.append(f'<p class="note">Scope: <code>'
                     f'{html.escape(str(coverage["scope"]))}</code></p>')
    parts.append('<table class="coverage">')
    for key in ("discovered", "analyzed", "skipped", "errors"):
        if key in coverage:
            parts.append(
                f'<tr><td class="key">{html.escape(key)}</td>'
                f'<td class="int">{html.escape(str(coverage[key]))}</td></tr>'
            )
    parts.append('</table>')
    if status and status != "COMPLETE":
        parts.append('<p class="note">Partial coverage. Findings describe the '
                     'analyzed subset only.</p>')
    return parts


def _render_chain_of_custody(artifact: dict[str, Any]) -> list[str]:
    parts = ['<h2>Chain of Custody</h2>']
    parts.append('<table class="custody">')
    for key in sorted(artifact):
        if "digest" in key.lower() and isinstance(artifact[key], str):
            parts.append(
                f'<tr><td class="key">{html.escape(key)}</td>'
                f'<td><code>{html.escape(str(artifact[key]))}</code></td></tr>'
            )
    parts.append('</table>')
    return parts


def _render_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return f'<pre>{html.escape(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))}</pre>'
    if isinstance(value, bool):
        return f'<span class="bool">{value}</span>'
    if isinstance(value, int):
        return f'<span class="int">{value}</span>'
    return html.escape(str(value))


_CSS = """
/* Shared palette with remember-the-seasons (same hackathon). Every text role
   clears WCAG AA against --bg: text 16.5:1, --dim 7.1:1, --g 8.0:1,
   --warn 10.1:1, --bad 5.5:1. */
:root {
  --g:#76b900; --g-dim:#5a9100;
  --bg:#0b0f0a; --p:#121810; --p2:#0d130b;
  --line:#22301c; --line2:#1a2414;
  --dim:#8fa383; --tx:#e7f0e3; --warn:#e8b33d; --bad:#d16a6a;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
}
body { font-family: var(--sans); margin: 0; padding: 20px; background: var(--bg); color: var(--tx); }
.container { max-width: 960px; margin: 0 auto; background: var(--p); padding: 40px; border: 1px solid var(--line); border-radius: 8px; }
h1 { margin-top: 0; color: var(--tx); }
h2 { margin-top: 32px; border-bottom: 1px solid var(--line); padding-bottom: 8px; color: var(--tx); font-size: 20px; }
h3 { color: var(--dim); font-size: 15px; }
.version { color: var(--dim); font-size: 14px; }
.digest { font-size: 12px; color: var(--dim); word-break: break-all; }
.digest code { background: var(--p2); border: 1px solid var(--line2); padding: 2px 4px; border-radius: 3px; }
.status { font-weight: bold; padding: 4px 8px; border-radius: 4px; display: inline-block; margin: 4px 0; }
.status.blocked { background: var(--p2); color: var(--warn); border: 1px solid var(--warn); }
.status.available { background: var(--p2); color: var(--g); border: 1px solid var(--g); }
.status-detail { font-size: 13px; color: var(--dim); margin-top: 4px; }
.outcome { font-size: 18px; padding: 8px 12px; border-radius: 4px; display: inline-block; margin: 8px 0; }
.outcome.accepted { background: var(--p2); color: var(--g); border: 1px solid var(--g); }
.outcome.rejected { background: var(--p2); color: var(--bad); border: 1px solid var(--bad); }
.rejection { color: var(--bad); font-size: 14px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { text-align: left; padding: 8px 12px; border: 1px solid var(--line); vertical-align: top; }
th { background: var(--p2); font-weight: 600; color: var(--dim); }
td.key { font-weight: 600; color: var(--dim); width: 200px; }
code { font-family: var(--mono); }
.findings th, .mutations th, .behavioral th, .custody th { font-size: 13px; }
.status-killed { color: var(--g); font-weight: bold; }
.status-survived { color: var(--warn); font-weight: bold; }
.status-abstained { color: var(--dim); font-weight: bold; }
.regression-yes { color: var(--bad); }
.regression-no { color: var(--g); }
.limitations { color: var(--dim); }
.limitations li { margin-bottom: 8px; }
.note { color: var(--dim); font-size: 13px; margin: 4px 0 12px; }
.outcome-abstained { color: var(--warn); font-weight: bold; }
.outcome-exercised { color: var(--g); }
.preconditions th, .excluded th, .coverage th, .corpus-inputs th { font-size: 13px; }
table.preconditions { table-layout: fixed; }
table.preconditions td:nth-child(1) { width: 20%; overflow-wrap: anywhere; }
table.preconditions td:nth-child(2) { width: 9%; }
table.preconditions td:nth-child(3) { width: 17%; }
table.preconditions td:nth-child(4) { width: 7%; text-align: right; }
table.preconditions td:nth-child(5) { width: 47%; }
table.preconditions code { font-size: 11px; word-break: break-word; }
.empty { color: var(--dim); font-style: italic; }
pre { background: var(--p2); border: 1px solid var(--line2); padding: 8px; border-radius: 4px; overflow-x: auto; font-size: 12px; font-family: var(--mono); }
.bool { color: var(--g); }
.int { color: var(--tx); }
.level { margin-bottom: 24px; padding: 16px; background: var(--p2); border: 1px solid var(--line2); border-radius: 6px; }
"""

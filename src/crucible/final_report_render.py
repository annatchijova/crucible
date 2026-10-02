"""Markdown, HTML, and PDF renderers over a sealed `crucible-final-report/v1`
artifact (final_report.py).

Every renderer here is a read-only projection, same discipline as
viewer.py's `render_artifact_html`: nothing here re-runs an audit,
recomputes a recommendation, or calls an LLM. The PDF renderer's section
shape (masthead/status banner, overview stats, a findings table per skill,
chain of custody, methodology) and its library choice (`reportlab`, pure
Python, no external binary) are adapted from VIGIA's Daubert-grade PDF
reporter by way of Anna's own `zaynor/src/zaynor/report.py::render_pdf`,
confirmed by reading that file in full -- reused because `render_pdf` there
already states it is reusing shape+library from VIGIA for the same reason.
The actual data model is new: ZAYNOR renders one `ZaynorAuthoritativeResult`
with a single verdict and MITRE-tagged findings; Crucible renders one report
that fans out per-skill, each with its own KEEP/NEEDS_CONFIRMATION/MODIFY/
DELETE recommendation and its own LLM narrative -- no code from zaynor's
renderer is copied, only the section shape and the reportlab usage pattern.

Methodology statement, chain-of-custody fields, and the escaping discipline
below are Crucible-specific, not copied from any other project.
"""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape as _xml_escape


class RenderError(RuntimeError):
    """A report could not be rendered."""


_RECOMMENDATION_TONE = {
    "DELETE": "fail",
    "MODIFY": "caution",
    "NEEDS_CONFIRMATION": "muted",
    "KEEP": "ok",
}

_METHODOLOGY = (
    "The recommendation for every skill (KEEP, NEEDS_CONFIRMATION, MODIFY, "
    "or DELETE) is computed by a deterministic rule over L2 audit findings "
    "and L2.5/L12 confirmation verdicts, before any language model is "
    "consulted. The model is given that decision as a fixed fact and asked "
    "only to explain it in prose, citing findings by id. Every finding id "
    "the model cites is checked after the fact against the sealed findings "
    "for that skill; an id that does not exist there is listed as an "
    "untraceable claim, not silently presented as evidence. report_digest "
    "is the canonical seal of this report: recompute it independently to "
    "confirm this rendering was not altered after the fact."
)


def _skill_rows(report: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return sorted(report.get("skills", {}).items())


def _counts_line(report: dict[str, Any]) -> str:
    by_rec = report.get("summary", {}).get("by_recommendation", {})
    order = ["DELETE", "MODIFY", "NEEDS_CONFIRMATION", "KEEP"]
    parts = [f"{label}: {by_rec.get(label, 0)}" for label in order if by_rec.get(label, 0)]
    return ", ".join(parts) if parts else "no skills in this corpus"


def _finding_line(finding: dict[str, Any], status: str) -> str:
    return (
        f"{finding.get('id', '?')} [{status}] {finding.get('class', '')} -- "
        f"{finding.get('evidence', '')}"
    )


def _status_for_finding(skill: dict[str, Any], finding_id: str) -> str:
    if finding_id in skill.get("confirmed_finding_ids", []):
        return "CONFIRMED"
    if finding_id in skill.get("rejected_finding_ids", []):
        return "REJECTED"
    if finding_id in skill.get("pending_finding_ids", []):
        return "PENDING"
    return "UNKNOWN"


def render_final_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Crucible Skill Quality Report",
        "",
        f"- **Report digest:** `{report.get('report_digest', '')}`",
        f"- **Audit digest:** `{report.get('audit_digest', '')}`",
        f"- **Confirmation digest:** `{report.get('confirmation_digest', '')}`",
        f"- **Skills scanned:** {report.get('skill_count', 0)}",
        f"- **Recommendations:** {_counts_line(report)}",
    ]
    if report.get("confirmation_digest_mismatch"):
        lines.append(
            "- **Warning:** the confirmation artifact does not match this audit; "
            "its verdicts were NOT trusted and affected findings are treated as pending."
        )
    lines += ["", "## Skills", ""]
    if not report.get("skills"):
        lines.append("No skills found in this corpus.")
    for skill_name, skill in _skill_rows(report):
        lines += [f"### {skill_name} -- {skill['recommendation']}", ""]
        if skill.get("narrative"):
            lines += [skill["narrative"], ""]
        elif skill.get("narration_blocked"):
            lines += [f"*Narration blocked: {skill.get('narration_error', 'unknown reason')}*", ""]
        elif skill.get("narration_error"):
            lines += [f"*Narration error: {skill['narration_error']}*", ""]
        if skill.get("untraceable_finding_ids"):
            lines += [
                f"**Untraceable claims flagged:** {', '.join(skill['untraceable_finding_ids'])} "
                "(cited by the narrative but not found in this skill's sealed findings)",
                "",
            ]
        if skill.get("findings"):
            lines.append("| Finding | Status | Class | Evidence |")
            lines.append("|---|---|---|---|")
            for finding in skill["findings"]:
                status = _status_for_finding(skill, finding.get("id", ""))
                evidence = str(finding.get("evidence", "")).replace("|", "\\|")
                lines.append(
                    f"| {finding.get('id', '')} | {status} | {finding.get('class', '')} | {evidence} |"
                )
            lines.append("")
    lines += ["## Methodology", "", _METHODOLOGY, ""]
    return "\n".join(lines)


def _escape_html(text: Any) -> str:
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _skill_card_html(skill_name: str, skill: dict[str, Any]) -> str:
    tone = _RECOMMENDATION_TONE.get(skill["recommendation"], "muted")
    narrative_html = (
        f"<p>{_escape_html(skill['narrative'])}</p>"
        if skill.get("narrative")
        else f"<p class='empty-state'>{_escape_html(skill.get('narration_error') or 'No narrative available.')}</p>"
    )
    untraceable_html = ""
    if skill.get("untraceable_finding_ids"):
        ids = ", ".join(_escape_html(i) for i in skill["untraceable_finding_ids"])
        untraceable_html = f"<p class='untraceable'>Untraceable claims flagged: {ids}</p>"
    rows = "".join(
        f"<tr><td><code>{_escape_html(f.get('id'))}</code></td>"
        f"<td>{_escape_html(_status_for_finding(skill, f.get('id', '')))}</td>"
        f"<td>{_escape_html(f.get('class'))}</td>"
        f"<td>{_escape_html(f.get('evidence'))}</td></tr>"
        for f in skill.get("findings", [])
    )
    table_html = (
        f"<table class='findings'><tr><th>Finding</th><th>Status</th><th>Class</th><th>Evidence</th></tr>{rows}</table>"
        if rows
        else "<p class='empty-state'>No findings for this skill.</p>"
    )
    return f"""<section class="skill-card tone-{tone}">
  <h2>{_escape_html(skill_name)} <span class="badge tone-{tone}">{_escape_html(skill['recommendation'])}</span></h2>
  {narrative_html}
  {untraceable_html}
  {table_html}
</section>"""


def render_final_report_html(report: dict[str, Any]) -> str:
    skill_cards = "".join(_skill_card_html(name, skill) for name, skill in _skill_rows(report)) or (
        "<p class='empty-state'>No skills in this corpus.</p>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crucible Skill Quality Report</title>
<style>
:root{{
  --bg:#f5f5f5; --card-bg:#fff; --ink:#1a1a2e; --ink-muted:#666; --rule:#e0e0e0;
  --ok-bg:#d4edda; --ok-ink:#155724; --fail-bg:#f8d7da; --fail-ink:#721c24;
  --caution-bg:#fff3cd; --caution-ink:#856404; --muted-bg:#e2e3e5; --muted-ink:#383d41;
}}
*{{box-sizing:border-box;}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;padding:24px;background:var(--bg);color:var(--ink);}}
.wrap{{max-width:980px;margin:0 auto;}}
header{{margin-bottom:24px;}}
h1{{margin:0 0 8px;}}
.meta{{font-size:13px;color:var(--ink-muted);}}
.meta code{{background:#eee;padding:1px 4px;border-radius:3px;word-break:break-all;}}
.skill-card{{background:var(--card-bg);border:1px solid var(--rule);border-radius:6px;padding:18px 20px;margin-bottom:16px;}}
.skill-card h2{{margin-top:0;display:flex;align-items:center;gap:10px;font-size:18px;}}
.badge{{font-size:12px;font-weight:700;padding:3px 10px;border-radius:12px;text-transform:uppercase;letter-spacing:.03em;}}
.badge.tone-ok, .tone-ok .badge{{background:var(--ok-bg);color:var(--ok-ink);}}
.badge.tone-fail, .tone-fail .badge{{background:var(--fail-bg);color:var(--fail-ink);}}
.badge.tone-caution, .tone-caution .badge{{background:var(--caution-bg);color:var(--caution-ink);}}
.badge.tone-muted, .tone-muted .badge{{background:var(--muted-bg);color:var(--muted-ink);}}
table.findings{{border-collapse:collapse;width:100%;margin-top:10px;font-size:13px;}}
table.findings th, table.findings td{{text-align:left;padding:6px 10px;border:1px solid var(--rule);vertical-align:top;}}
table.findings th{{background:#fafafa;}}
.empty-state{{color:#999;font-style:italic;}}
.untraceable{{color:var(--fail-ink);background:var(--fail-bg);padding:6px 10px;border-radius:4px;font-size:13px;}}
footer{{margin-top:28px;font-size:12px;color:var(--ink-muted);border-top:1px solid var(--rule);padding-top:14px;}}
@media print {{ body{{background:#fff;}} .skill-card{{break-inside:avoid;}} }}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1>Crucible Skill Quality Report</h1>
<p class="meta">
Report digest: <code>{_escape_html(report.get('report_digest', ''))}</code><br>
Skills scanned: {report.get('skill_count', 0)} &mdash; {_escape_html(_counts_line(report))}
</p>
</header>
{skill_cards}
<footer>{_escape_html(_METHODOLOGY)}</footer>
</div>
</body>
</html>
"""


def render_final_report_pdf(report: dict[str, Any]) -> bytes:
    """Render via reportlab, imported lazily so the rest of Crucible has no
    hard dependency on it."""
    try:
        from io import BytesIO

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RenderError(
            "PDF reports require the optional 'reportlab' dependency: pip install reportlab"
        ) from exc

    tone_colors = {
        "ok": (colors.HexColor("#d4edda"), colors.HexColor("#155724")),
        "fail": (colors.HexColor("#f8d7da"), colors.HexColor("#721c24")),
        "caution": (colors.HexColor("#fff3cd"), colors.HexColor("#856404")),
        "muted": (colors.HexColor("#e2e3e5"), colors.HexColor("#383d41")),
    }

    def _footer(canvas, doc_) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        digest = str(report.get("report_digest", ""))[:24]
        canvas.drawString(36, 20, f"Crucible sealed report -- report_digest {digest}...")
        canvas.drawRightString(A4[0] - 36, 20, f"Page {doc_.page}")
        canvas.restoreState()

    styles = getSampleStyleSheet()
    cell_style = styles["Normal"].clone("CrucibleCell")
    cell_style.fontSize = 8
    cell_style.leading = 10
    cell_style.wordWrap = "CJK"
    header_style = styles["Normal"].clone("CrucibleHeader")
    header_style.fontSize = 8
    header_style.leading = 10

    def _table(rows: list[list[str]], col_widths: list[int], row_tones: list[str | None] | None = None) -> Table:
        wrapped = [
            [
                Paragraph(_xml_escape(str(cell)).replace("\n", "<br/>") or "&#160;", header_style if r == 0 else cell_style)
                for cell in row
            ]
            for r, row in enumerate(rows)
        ]
        table = Table(wrapped, repeatRows=1, colWidths=col_widths)
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        if row_tones:
            for i, tone in enumerate(row_tones, start=1):
                if tone is not None:
                    bg, _ = tone_colors.get(tone, tone_colors["muted"])
                    commands.append(("BACKGROUND", (0, i), (-1, i), bg))
        table.setStyle(TableStyle(commands))
        return table

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Crucible Skill Quality Report")
    story: list[Any] = [
        Paragraph("Crucible Skill Quality Report", styles["Title"]),
        Spacer(1, 8),
        Paragraph(f"Report digest: {_xml_escape(str(report.get('report_digest', '')))}", styles["Normal"]),
        Paragraph(f"Skills scanned: {report.get('skill_count', 0)} -- {_xml_escape(_counts_line(report))}", styles["Normal"]),
    ]
    if report.get("confirmation_digest_mismatch"):
        story.append(Paragraph(
            "WARNING: the confirmation artifact does not match this audit; "
            "its verdicts were not trusted.", styles["Normal"],
        ))
    story.append(Spacer(1, 12))

    for skill_name, skill in _skill_rows(report):
        tone = _RECOMMENDATION_TONE.get(skill["recommendation"], "muted")
        bg, ink = tone_colors.get(tone, tone_colors["muted"])
        banner_style = styles["Normal"].clone(f"Banner-{skill_name}")
        banner_style.fontSize = 11
        banner_style.textColor = ink
        banner = Table(
            [[Paragraph(f"{_xml_escape(skill_name)} -- {_xml_escape(skill['recommendation'])}", banner_style)]],
            colWidths=[523],
        )
        banner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("BOX", (0, 0), (-1, -1), 0.5, ink),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story += [banner, Spacer(1, 6)]
        if skill.get("narrative"):
            story.append(Paragraph(_xml_escape(skill["narrative"]).replace("\n", "<br/>"), styles["Normal"]))
        else:
            story.append(Paragraph(
                _xml_escape(skill.get("narration_error") or "No narrative available."), styles["Normal"],
            ))
        if skill.get("untraceable_finding_ids"):
            story.append(Paragraph(
                f"Untraceable claims flagged: {_xml_escape(', '.join(skill['untraceable_finding_ids']))}",
                styles["Normal"],
            ))
        findings = skill.get("findings", [])
        if findings:
            rows = [["Finding", "Status", "Class", "Evidence"]]
            row_tones: list[str | None] = [None]
            for finding in findings:
                rows.append([
                    finding.get("id", ""), _status_for_finding(skill, finding.get("id", "")),
                    finding.get("class", ""), finding.get("evidence", ""),
                ])
                row_tones.append(None)
            story.append(Spacer(1, 4))
            story.append(_table(rows, [70, 65, 110, 278], row_tones))
        story.append(Spacer(1, 14))

    story += [Paragraph("Methodology", styles["Heading2"]), Paragraph(_METHODOLOGY, styles["Normal"])]
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()

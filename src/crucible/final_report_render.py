"""Markdown, HTML, and PDF renderers over a sealed `crucible-final-report/v2`
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
CONSOLIDATE recommendation and its own LLM narrative -- no code from zaynor's
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
    "CONSOLIDATE": "fail",
    "MODIFY": "caution",
    "NEEDS_CONFIRMATION": "muted",
    "KEEP": "ok",
}

_METHODOLOGY = (
    "The recommendation for every skill (KEEP, NEEDS_CONFIRMATION, MODIFY, "
    "or CONSOLIDATE) is computed by a deterministic rule over L2 audit findings "
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
    order = ["CONSOLIDATE", "MODIFY", "NEEDS_CONFIRMATION", "KEEP"]
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
    if finding_id in skill.get("consolidation_finding_ids", []):
        return "CONFIRMED"
    if finding_id in skill.get("rejected_finding_ids", []):
        return "REJECTED"
    if finding_id in skill.get("pending_finding_ids", []):
        return "PENDING"
    return "UNKNOWN"


_SHARED_TEXT_LIMIT = 10

_SHARED_TEXT_NOTE = (
    "The same rule text appears verbatim in several skills. A repeated block "
    "is a candidate for one shared skill or reference document; it is not by "
    "itself a defect, and editing one copy leaves the others behind."
)

_GROUP_NOTE = (
    "Each group is a set of skills joined by confirmed redundancy pairs. The "
    "recommendation is to merge each group into one skill; which member "
    "survives, and what the merged text says, is not decided here. Run "
    "consolidation (--consolidate-all) to have a merge proposed and checked "
    "by the deterministic gate."
)


def _sentence(text: str) -> str:
    return f"{text[:1].upper()}{text[1:]}." if text and not text.endswith(".") else text


def _abstained(report: dict[str, Any], check_class: str) -> dict[str, Any] | None:
    preconditions = report.get("corpus", {}).get("preconditions") or {}
    for check in preconditions.get("checks", []):
        if check.get("check_class") == check_class and check.get("outcome") == "ABSTAINED":
            return check
    return None


def _corpus_blocks(report: dict[str, Any]) -> list[dict[str, Any]]:
    """The corpus-level sections as plain data, shared by every renderer.

    Each block is {"title", "intro", "items": [{"heading", "lines"}],
    "empty"}; a renderer only decides how to lay them out.
    """
    corpus = report.get("corpus") or {}
    blocks: list[dict[str, Any]] = []

    groups = corpus.get("consolidation_groups", [])
    blocks.append({
        "title": "Duplicate skills to consolidate",
        "intro": _GROUP_NOTE,
        "items": [
            {
                "heading": f"{group['size']} skills into 1: {', '.join(group['members'])}",
                "lines": [
                    f"{fid}: {evidence}"
                    for fid, evidence in zip(group["finding_ids"], group["evidence"])
                ],
            }
            for group in groups
        ],
        "empty": "No confirmed duplicate group in this corpus.",
    })

    contradictions = corpus.get("contradictions", [])
    abstained = [
        check for check in (
            _abstained(report, "NORMATIVE_CONFLICT"),
            _abstained(report, "CONDITIONAL_CONTRADICTION"),
        ) if check
    ]
    if contradictions:
        empty = ""
    elif abstained:
        empty = (
            "Not evaluated: the contradiction checks abstained because "
            f"{abstained[0]['reason']}. This is not evidence that the skills "
            "agree with each other."
        )
    else:
        empty = "No contradiction found between rules that state a comparable subject."
    blocks.append({
        "title": "Contradictions between rules",
        "intro": "",
        "items": [
            {
                "heading": f"{item['finding_id']} {item['class']} (reported on {item['skill']})",
                "lines": [item["evidence"], f"Risk: {item['risk']}"],
            }
            for item in contradictions
        ],
        "empty": empty,
    })

    shared = corpus.get("shared_rule_texts", [])
    items = [
        {
            "heading": f"{item['skill_count']} skills share: {item['text']}",
            "lines": [", ".join(item["skills"])],
        }
        for item in shared[:_SHARED_TEXT_LIMIT]
    ]
    intro = _SHARED_TEXT_NOTE
    if len(shared) > _SHARED_TEXT_LIMIT:
        intro += f" Showing the {_SHARED_TEXT_LIMIT} most repeated of {len(shared)}."
    blocks.append({
        "title": "Rule text repeated across skills",
        "intro": intro,
        "items": items,
        "empty": "No rule text is repeated verbatim across skills.",
    })

    preconditions = corpus.get("preconditions") or {}
    not_run = [c for c in preconditions.get("checks", []) if c.get("outcome") == "ABSTAINED"]
    blocks.append({
        "title": "What was not analyzed",
        "intro": _sentence(preconditions.get("limitation", "")),
        "items": [
            {
                "heading": f"{check['check_class']} abstained",
                "lines": [f"requires {check['requires']}, observed {check['observed']}: {check['reason']}"],
            }
            for check in not_run
        ],
        "empty": "Every check with a precondition received the input it needs.",
    })
    return blocks


def _corpus_markdown(report: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for block in _corpus_blocks(report):
        lines += [f"## {block['title']}", ""]
        if block["intro"]:
            lines += [block["intro"], ""]
        if not block["items"]:
            lines += [block["empty"], ""]
        for item in block["items"]:
            lines.append(f"- **{item['heading']}**")
            lines += [f"  - {line}" for line in item["lines"]]
        if block["items"]:
            lines.append("")
    return lines


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
    lines.append("")
    lines += _corpus_markdown(report)
    lines += ["## Skills", ""]
    if not report.get("skills"):
        lines.append("No skills found in this corpus.")
    for skill_name, skill in _skill_rows(report):
        lines += [f"### {skill_name} -- {skill['recommendation']}", ""]
        if skill.get("consolidation_group"):
            others = [n for n in skill["consolidation_group"] if n != skill_name]
            lines += [f"**Consolidate with:** {', '.join(others)}", ""]
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
    group_html = ""
    if skill.get("consolidation_group"):
        others = ", ".join(_escape_html(n) for n in skill["consolidation_group"] if n != skill_name)
        group_html = f"<p><strong>Consolidate with:</strong> {others}</p>"
    return f"""<section class="skill-card tone-{tone}">
  <h2>{_escape_html(skill_name)} <span class="badge tone-{tone}">{_escape_html(skill['recommendation'])}</span></h2>
  {group_html}
  {narrative_html}
  {untraceable_html}
  {table_html}
</section>"""


def _corpus_html(report: dict[str, Any]) -> str:
    parts = []
    for block in _corpus_blocks(report):
        body = ""
        if block["intro"]:
            body += f"<p class='intro'>{_escape_html(block['intro'])}</p>"
        if not block["items"]:
            body += f"<p class='empty-state'>{_escape_html(block['empty'])}</p>"
        else:
            body += "<ul>" + "".join(
                f"<li><strong>{_escape_html(item['heading'])}</strong>"
                + ("<ul>" + "".join(f"<li>{_escape_html(line)}</li>" for line in item["lines"]) + "</ul>"
                   if item["lines"] else "")
                + "</li>"
                for item in block["items"]
            ) + "</ul>"
        parts.append(f"<section class='corpus-card'><h2>{_escape_html(block['title'])}</h2>{body}</section>")
    return "".join(parts)


def render_final_report_html(report: dict[str, Any]) -> str:
    corpus_cards = _corpus_html(report)
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
.corpus-card{{background:var(--card-bg);border:1px solid var(--rule);border-left:4px solid var(--ink);border-radius:6px;padding:16px 20px;margin-bottom:16px;}}
.corpus-card h2{{margin-top:0;font-size:18px;}}
.corpus-card li{{margin:4px 0;overflow-wrap:anywhere;}}
.intro{{color:var(--ink-muted);font-size:14px;}}
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
{corpus_cards}
<h2>Skills</h2>
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

    for block in _corpus_blocks(report):
        story.append(Paragraph(_xml_escape(block["title"]), styles["Heading2"]))
        if block["intro"]:
            story.append(Paragraph(_xml_escape(block["intro"]), styles["Normal"]))
        if not block["items"]:
            story.append(Paragraph(_xml_escape(block["empty"]), styles["Italic"]))
        for item in block["items"]:
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<b>{_xml_escape(item['heading'])}</b>", styles["Normal"]))
            for line in item["lines"]:
                story.append(Paragraph(_xml_escape(line), cell_style))
        story.append(Spacer(1, 10))

    story.append(Paragraph("Skills", styles["Heading2"]))
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
        if skill.get("consolidation_group"):
            others = ", ".join(n for n in skill["consolidation_group"] if n != skill_name)
            story.append(Paragraph(f"<b>Consolidate with:</b> {_xml_escape(others)}", styles["Normal"]))
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

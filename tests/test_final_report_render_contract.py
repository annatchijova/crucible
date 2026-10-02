"""Contract tests for the L15 markdown/HTML/PDF renderers."""

import pytest

from crucible.final_report_render import (
    RenderError,
    render_final_report_html,
    render_final_report_markdown,
    render_final_report_pdf,
)


def _report(**overrides):
    base = {
        "schema_version": "crucible-final-report/v1",
        "report_digest": "sha256:deadbeef",
        "audit_digest": "sha256:a",
        "confirmation_digest": "sha256:c",
        "confirmation_digest_mismatch": False,
        "skill_count": 1,
        "summary": {"by_recommendation": {"MODIFY": 1}, "total_skills": 1},
        "skills": {
            "retrier": {
                "recommendation": "MODIFY",
                "confirmed_finding_ids": ["finding-0001"],
                "rejected_finding_ids": [],
                "pending_finding_ids": [],
                "findings": [
                    {
                        "id": "finding-0001",
                        "class": "UNBOUNDED_RETRY",
                        "evidence": "retries MUST continue until success",
                    }
                ],
                "narrative": "The retry budget is unbounded (finding-0001); add a cap.",
                "narration_blocked": False,
                "narration_error": None,
                "cited_finding_ids": ["finding-0001"],
                "untraceable_finding_ids": [],
            }
        },
    }
    base.update(overrides)
    return base


def test_markdown_includes_digests_recommendation_and_finding_table():
    text = render_final_report_markdown(_report())
    assert "sha256:deadbeef" in text
    assert "retrier -- MODIFY" in text
    assert "finding-0001" in text
    assert "UNBOUNDED_RETRY" in text
    assert "The retry budget is unbounded" in text


def test_markdown_flags_untraceable_claims():
    report = _report()
    report["skills"]["retrier"]["untraceable_finding_ids"] = ["finding-9999"]
    text = render_final_report_markdown(report)
    assert "Untraceable claims flagged" in text
    assert "finding-9999" in text


def test_markdown_handles_empty_corpus():
    report = _report(skills={}, summary={"by_recommendation": {}, "total_skills": 0}, skill_count=0)
    text = render_final_report_markdown(report)
    assert "No skills found" in text


def test_html_escapes_narrative_content():
    report = _report()
    report["skills"]["retrier"]["narrative"] = "<script>alert(1)</script> & other text"
    html = render_final_report_html(report)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html


def test_html_includes_recommendation_badge_and_findings_table():
    html = render_final_report_html(_report())
    assert "MODIFY" in html
    assert "finding-0001" in html
    assert "UNBOUNDED_RETRY" in html


def test_html_handles_empty_corpus():
    report = _report(skills={}, summary={"by_recommendation": {}, "total_skills": 0}, skill_count=0)
    html = render_final_report_html(report)
    assert "No skills in this corpus" in html


def test_pdf_renders_valid_bytes_with_real_narrative_and_unicode():
    pytest.importorskip("reportlab")
    report = _report()
    report["skills"]["retrier"]["narrative"] = "Uses an em dash — and ünïcödé text."
    pdf_bytes = render_final_report_pdf(report)
    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 100


def test_pdf_renders_an_untraceable_warning():
    pytest.importorskip("reportlab")
    report = _report()
    report["skills"]["retrier"]["untraceable_finding_ids"] = ["finding-9999"]
    pdf_bytes = render_final_report_pdf(report)
    assert pdf_bytes[:5] == b"%PDF-"


def test_pdf_renders_a_blocked_narration_without_crashing():
    pytest.importorskip("reportlab")
    report = _report()
    report["skills"]["retrier"]["narrative"] = None
    report["skills"]["retrier"]["narration_blocked"] = True
    report["skills"]["retrier"]["narration_error"] = "NEBIUS_API_KEY not set"
    pdf_bytes = render_final_report_pdf(report)
    assert pdf_bytes[:5] == b"%PDF-"


def test_missing_reportlab_raises_a_clear_render_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "reportlab" or name.startswith("reportlab."):
            raise ImportError("simulated missing reportlab")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)
    with pytest.raises(RenderError, match="reportlab"):
        render_final_report_pdf(_report())


def test_pdf_handles_empty_corpus():
    pytest.importorskip("reportlab")
    report = _report(skills={}, summary={"by_recommendation": {}, "total_skills": 0}, skill_count=0)
    pdf_bytes = render_final_report_pdf(report)
    assert pdf_bytes[:5] == b"%PDF-"

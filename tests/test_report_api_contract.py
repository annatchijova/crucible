"""Contract tests for the model-free report endpoints."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from crucible.api import create_app  # noqa: E402

SKILL = (
    "---\nname: deploy-fast\ndescription: Ship releases quickly.\n---\n\n"
    "# Deploy\n\nReleases MUST skip the staging environment.\n"
)


def test_report_skill_returns_a_sealed_report_and_its_html(monkeypatch) -> None:
    """Invariant: the endpoint never calls a model -- confirmation and
    narration report themselves as not run -- even with a key configured.
    Mutation: build the report with the Nebius executors -> a network call
    is attempted -> red."""
    monkeypatch.setenv("NEBIUS_API_KEY", "test-not-a-key")

    def no_network(*args, **kwargs):
        raise AssertionError("a model was called")

    monkeypatch.setattr("urllib.request.urlopen", no_network)
    client = TestClient(create_app())
    resp = client.post("/report/skill", json={"skill_text": SKILL, "skill_name": "deploy-fast"})
    assert resp.status_code == 200
    body = resp.json()
    report = body["report"]
    assert report["schema_version"] == "crucible-final-report/v2"
    assert report["input"]["scope"] == "single-skill"
    assert report["report_digest"].startswith("sha256:")
    assert report["executive_summary"]["blocked"] is True
    assert "does not call a model" in report["executive_summary"]["error"]
    assert body["html"].startswith("<!doctype html>")


def test_report_directory_refuses_a_missing_directory() -> None:
    client = TestClient(create_app())
    resp = client.post("/report/directory", json={"directory": "/no/such/dir"})
    assert resp.status_code == 400


def test_demo_page_offers_the_report_in_a_sandboxed_frame() -> None:
    page = TestClient(create_app()).get("/").text
    assert "Report (no model)" in page
    assert "frame.setAttribute('sandbox', '')" in page

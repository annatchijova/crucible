"""The HTTP surface itself, which no test exercised before.

Every existing API test calls scan_skill_text() and friends as Python
functions. That left the actual routes untested, and both POST endpoints were
unreachable over HTTP: api.py used `from __future__ import annotations`, so
`req: ScanSkillRequest` became the string "ScanSkillRequest", which FastAPI
could not resolve against the module globals because the request models are
defined inside create_app() to keep pydantic optional. FastAPI then treated
the body model as a query parameter and every POST returned 422.

These tests assert the route wiring rather than issuing requests, so they need
no HTTP client dependency and still fail on exactly that defect.
"""
import pytest

fastapi = pytest.importorskip("fastapi", reason="API extra not installed")

from crucible.api import create_app


@pytest.fixture(scope="module")
def app():
    return create_app()


def route_for(app, path):
    return next(r for r in app.routes if getattr(r, "path", None) == path)


def test_every_documented_route_is_registered(app):
    paths = {getattr(r, "path", None) for r in app.routes}
    assert {"/health", "/", "/scan/skill", "/scan/directory", "/scan/installed"} <= paths


@pytest.mark.parametrize("path", ["/scan/skill", "/scan/directory"])
def test_post_routes_take_a_request_body_not_a_query_parameter(app, path):
    """Invariant: the body model resolves. Mutation: restore the postponed
    annotations import in api.py -> body_field becomes None and 'req' appears
    as a query parameter, which is the 422 bug this test exists for."""
    route = route_for(app, path)
    assert sorted(route.methods) == ["POST"]
    assert route.body_field is not None, f"{path}: body model did not resolve"
    assert [p.name for p in route.dependant.query_params] == [], (
        f"{path}: the body model leaked into the query string"
    )


def test_scan_skill_body_declares_the_documented_fields(app):
    fields = route_for(app, "/scan/skill").body_field.field_info.annotation.model_fields
    assert set(fields) == {"skill_text", "skill_name"}
    assert fields["skill_text"].is_required()
    assert fields["skill_name"].default == "uploaded"


def test_scan_directory_body_declares_the_documented_field(app):
    fields = route_for(app, "/scan/directory").body_field.field_info.annotation.model_fields
    assert set(fields) == {"directory"}
    assert fields["directory"].is_required()


def test_installed_scan_is_a_get_with_no_parameters(app):
    route = route_for(app, "/scan/installed")
    assert sorted(route.methods) == ["GET"]
    assert route.body_field is None
    assert [p.name for p in route.dependant.query_params] == []


def test_api_module_does_not_postpone_annotations():
    """The models are local to create_app(), so postponed annotations break
    FastAPI's body resolution. Guard the cause, not only the symptom."""
    import pathlib
    lines = pathlib.Path("src/crucible/api.py").read_text(encoding="utf-8").splitlines()
    # Match the import statement, not a comment that explains why it is absent.
    assert not [line for line in lines
                if line.strip() == "from __future__ import annotations"]

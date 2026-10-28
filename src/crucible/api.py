"""Public HTTP API for scanning skills (L11).

Three input modes:
1. Single skill: POST /scan/skill with a SKILL.md body.
2. Directory: POST /scan/directory with a path to a directory of skills.
3. Installed skills: GET /scan/installed scans the user's installed skills.

The API is a thin wrapper over the deterministic compiler and auditor.
It does NOT make decisions, does NOT call an LLM, and does NOT modify the
input. It compiles, audits, and returns the sealed artifact.

The API is stateless: no input is retained after the response is sent.
"""
# Deliberately no `from __future__ import annotations`. The request models are
# defined inside create_app() so that pydantic stays an optional dependency,
# and postponed annotations would turn `req: ScanSkillRequest` into the string
# "ScanSkillRequest", which FastAPI cannot resolve against this module's
# globals -- it then treats the body model as a query parameter and every POST
# fails with 422. Every annotation here is a builtin generic or a name already
# in scope, so eager evaluation is safe on the supported Python floor (3.11+).

import contextlib
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Iterator, Sequence

from .auditor import audit_corpus
from .compiler import (
    compile_corpus, compile_skill_file, _discover_corpus, _read_skill_bytes,
    _scan_corpus_directory, _TraversalBudget, _file_identity,
)
from .ir import digest_payload

_MAX_COLLECTION_DIRECTORIES = 10_000
_MAX_COLLECTION_DISCOVERY_ENTRIES = 100_000
_MAX_COLLECTION_BYTES = 20_000_000
_MAX_EXPLICIT_SCAN_ROOTS = 256


def _coverage_summary(scope: str, discovered: int) -> dict[str, Any]:
    """Return the shared coverage counts without changing the sealed audit."""
    return {
        'scope': scope,
        'status': 'COMPLETE' if discovered else 'EMPTY',
        'discovered': discovered,
        'analyzed': discovered,
        'skipped': 0,
        'errors': 0,
    }


class _CollectionLimitError(ValueError):
    """A whole-scan limit, not an error confined to one package."""
from .graph import build_composition_graph


_NO_MODEL = (
    "this endpoint does not call a model; run --narrate from the CLI for "
    "confirmation and narration"
)


class _ModelNotRequested:
    """Executor for the report endpoints: every model step reports itself as
    not run. Confirmation is BLOCKED and narration is blocked with this
    reason, so the report shows what a model would add instead of faking it."""

    model = "none"

    def is_available(self) -> bool:
        return False

    def execute(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return {"output": "", "error": _NO_MODEL, "model": "none", "blocked": True}


def _report_payload(root: str, scope: dict[str, Any]) -> dict[str, Any]:
    from .final_report import build_final_report
    from .final_report_render import render_final_report_html

    report = build_final_report(
        root, _ModelNotRequested(), _ModelNotRequested(), input_scope=scope
    )
    return {"report": report, "html": render_final_report_html(report)}


def report_skill_text(skill_text: str, skill_name: str = "uploaded") -> dict[str, Any]:
    """The narrated report's deterministic part for one pasted SKILL.md."""
    _validate_skill_text(skill_text)
    safe_name = _sanitize_skill_name(skill_name)
    with tempfile.TemporaryDirectory(prefix="crucible-report-") as tmpdir:
        skill_dir = Path(tmpdir) / safe_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(skill_text, encoding="utf-8")
        return _report_payload(tmpdir, {"scope": "single-skill"})


def report_directory(directory: str) -> dict[str, Any]:
    """The narrated report's deterministic part for a directory of skills."""
    _validate_directory(directory)
    return _report_payload(directory, {"scope": "directory"})


def report_installed() -> dict[str, Any]:
    """The narrated report's deterministic part for the installed skills."""
    with stage_installed_skills() as stage:
        if stage.root is None:
            raise ValueError(stage.error or "no installed skills found")
        return _report_payload(stage.root, {"scope": "installed", "coverage": stage.coverage})


def scan_skill_text(skill_text: str, skill_name: str = "uploaded") -> dict[str, Any]:
    """Compile and audit a single SKILL.md provided as text.

    The skill is written to a temporary directory, compiled, audited, and
    the temporary directory is removed. No input is retained.

    Returns the audit artifact (crucible-audit/v2) with the L3 graph.
    The full L1 IR (including body_text) is NOT returned to prevent
    information disclosure (RT-03).
    """
    _validate_skill_text(skill_text)
    safe_name = _sanitize_skill_name(skill_name)
    with tempfile.TemporaryDirectory(prefix="crucible-scan-") as tmpdir:
        skill_dir = Path(tmpdir) / safe_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(skill_text, encoding="utf-8")
        ir = compile_corpus(tmpdir)
        audit = audit_corpus(ir)
        graph = build_composition_graph(ir, audit)
        return {
            "audit": audit,
            "ir": _redact_ir(ir),
            "graph": graph,
            "coverage": _coverage_summary('single-skill-text', len(ir['skills'])),
        }


def scan_directory(directory: str) -> dict[str, Any]:
    """Compile and audit a directory of skills.

    The directory must exist and contain at least one SKILL.md file.
    Returns the audit artifact with the L3 graph. The full L1 IR
    (including body_text) is NOT returned to prevent information
    disclosure (RT-03).
    """
    _validate_directory(directory)
    ir = compile_corpus(directory, max_skills=_MAX_SCAN_SKILLS)
    audit = audit_corpus(ir)
    graph = build_composition_graph(ir, audit)
    return {
        "audit": audit,
        "ir": _redact_ir(ir),
        "graph": graph,
        "coverage": _coverage_summary('local-directory-skills', len(ir['skills'])),
    }


def _installed_children(root: Path, budget: _TraversalBudget,
                        *, identities: dict | None = None) -> list[Path]:
    """Bound the initial listing before sorting, including non-package entries."""
    budget.add_directory()
    if identities is None:
        identities = {}
    identities[root] = _file_identity(root.stat(follow_symlinks=False))
    paths = []
    with _scan_corpus_directory(root, identities=identities) as children:
        for child in children:
            budget.add_entry()
            path = root / child.name
            if child.is_dir(follow_symlinks=False):
                identities[path] = _file_identity(child.stat(follow_symlinks=False))
            paths.append(path)
    return sorted(paths)


class InstalledStage:
    """Installed skills staged into one temporary directory for compiling.

    ``root`` is None when nothing was staged; ``error`` then says why.
    """

    def __init__(self, root: str | None, coverage: dict[str, Any],
                 skipped_duplicates: list[dict[str, str]], searched: list[str],
                 error: str | None) -> None:
        self.root = root
        self.coverage = coverage
        self.skipped_duplicates = skipped_duplicates
        self.searched = searched
        self.error = error


@contextlib.contextmanager
def stage_installed_skills(
    roots: Sequence[str | os.PathLike[str]] | None = None,
) -> Iterator[InstalledStage]:
    """Stage the user's installed skills into a temporary directory.

    Shared by the installed scan and the installed narrated report, so both
    read exactly the same packages under the same bounds. The directory is
    removed when the context exits.
    """
    if roots is None:
        search_roots = _standard_skill_dirs()
        skill_dirs = _find_installed_skill_dirs()
    else:
        search_roots = _normalize_explicit_roots(roots)
        skill_dirs = search_roots

    def coverage_report(items: list[dict[str, str]], analyzed: int) -> dict[str, Any]:
        skipped = sum(item['status'] == 'SKIPPED_DUPLICATE' for item in items)
        return {
            'scope': 'installed-direct-child-packages',
            'status': 'EMPTY' if not items else ('PARTIAL' if skipped else 'COMPLETE'),
            'discovered': len(items),
            'analyzed': analyzed,
            'skipped': skipped,
            'errors': 0,
            'items': items,
            'searched': [str(p) for p in search_roots],
        }

    if not skill_dirs:
        yield InstalledStage(
            None, coverage_report([], 0), [], [str(p) for p in search_roots],
            "no installed skills found in standard directories",
        )
        return
    # Stage only compiler inputs, with source identity and byte checks before
    # writing. Preserve nested SKILL.md paths and historical package precedence.
    skipped_duplicates: list[dict[str, str]] = []
    coverage_items: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="crucible-installed-") as tmpdir:
        count = 0
        staged_skills = 0
        staged_bytes = 0
        traversal_budget = _TraversalBudget()
        for skill_dir in skill_dirs:
            identities = {}
            for skill_path in _installed_children(
                skill_dir, traversal_budget, identities=identities
            ):
                if not skill_path.is_dir():
                    continue
                skill_md = skill_path / "SKILL.md"
                if not skill_md.exists():
                    continue
                dest = Path(tmpdir) / skill_path.name
                if dest.exists():
                    coverage_items.append({
                        'source_path': str(skill_md),
                        'skill_name': skill_path.name,
                        'status': 'SKIPPED_DUPLICATE',
                    })
                    skipped_duplicates.append({
                        "skill_name": skill_path.name,
                        "skipped_from": str(skill_dir),
                    })
                    continue
                paths = _discover_corpus(
                    skill_path, _MAX_SCAN_SKILLS - staged_skills,
                    identities=identities, budget=traversal_budget,
                )
                if skill_md not in paths:
                    raise ValueError('installed package entry point disappeared during discovery')
                for source in paths:
                    if source.is_symlink():
                        raise ValueError('symlinked SKILL.md is not allowed')
                    raw = _read_skill_bytes(
                        source, min(1_000_000, _MAX_COLLECTION_BYTES - staged_bytes),
                        identities=identities,
                    )
                    target = dest / source.relative_to(skill_path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
                    staged_bytes += len(raw)
                    staged_skills += 1
                coverage_items.append({
                    'source_path': str(skill_md),
                    'skill_name': skill_path.name,
                    'status': 'ANALYZED',
                })
                count += 1
        if count == 0:
            yield InstalledStage(
                None, coverage_report(coverage_items, count), skipped_duplicates,
                [str(p) for p in skill_dirs],
                "no SKILL.md files found in installed skill directories",
            )
            return
        yield InstalledStage(
            tmpdir, coverage_report(coverage_items, count), skipped_duplicates,
            [str(p) for p in search_roots], None,
        )


def scan_installed_skills(
    roots: Sequence[str | os.PathLike[str]] | None = None,
) -> dict[str, Any]:
    """Scan the user's installed skills.

    Searches the standard skill directories:
    - ~/.config/devin/skills/
    - ~/.claude/skills/
    - ~/.local/share/devin/skills/
    - ~/.codex/skills/ (direct child skill packages)

    Returns the audit artifact with the L1 IR and L3 graph.
    """
    with stage_installed_skills(roots) as stage:
        if stage.root is None:
            return {
                "audit": None,
                "ir": None,
                "graph": None,
                "error": stage.error,
                "skipped_duplicates": stage.skipped_duplicates,
                "searched": stage.searched,
                "coverage": stage.coverage,
            }
        ir = compile_corpus(stage.root, max_skills=_MAX_SCAN_SKILLS)
        audit = audit_corpus(ir)
        graph = build_composition_graph(ir, audit)
        return {
            "audit": audit,
            "ir": _redact_ir(ir),
            "graph": graph,
            "skipped_duplicates": stage.skipped_duplicates,
            "coverage": stage.coverage,
        }


def scan_installed_collection(
    roots: Sequence[str | os.PathLike[str]] | None = None,
) -> dict[str, Any]:
    """Audit nested packages independently; names need not be globally unique.

    Directory symlinks are recorded but never followed. Per-package errors
    remain in coverage; this mode makes no cross-package composition claim.
    Explicit roots are supported for local Python callers; omitted roots retain
    standard discovery.
    """
    search_roots = (
        _standard_skill_dirs() if roots is None else _normalize_explicit_roots(roots)
    )
    entries = []
    directories_seen = 0
    discovery_entries_seen = 0
    bytes_seen = 0

    def add_entry(entry):
        if len(entries) >= _MAX_SCAN_SKILLS:
            raise _CollectionLimitError('installed collection exceeds scan entry limit')
        entries.append(entry)

    def admit_directory():
        nonlocal directories_seen
        directories_seen += 1
        if directories_seen > _MAX_COLLECTION_DIRECTORIES:
            raise _CollectionLimitError('installed collection exceeds directory limit')

    def walk(root, identities):
        nonlocal discovery_entries_seen
        admit_directory()
        pending = [root]
        while pending:
            directory = pending.pop()
            dirs = []
            files = []
            try:
                with _scan_corpus_directory(directory, identities=identities) as children:
                    for child in children:
                        discovery_entries_seen += 1
                        if discovery_entries_seen > _MAX_COLLECTION_DISCOVERY_ENTRIES:
                            raise _CollectionLimitError('installed collection exceeds discovery entry limit')
                        path = directory / child.name
                        if child.name == 'SKILL.md':
                            files.append(child.name)
                            identities[path] = _file_identity(child.stat(follow_symlinks=False))
                        if child.is_symlink():
                            if child.name != 'SKILL.md':
                                add_entry({'source_path': str(path), 'status': 'ERROR',
                                           'error': 'symlinked collection entry is not allowed'})
                        elif child.is_dir(follow_symlinks=False):
                            admit_directory()
                            identities[path] = _file_identity(child.stat(follow_symlinks=False))
                            dirs.append(path)
            except _CollectionLimitError:
                raise
            except (OSError, ValueError) as exc:
                add_entry({'source_path': str(directory), 'status': 'ERROR',
                           'error': str(exc)})
                continue
            yield directory, files
            pending.extend(sorted(dirs, reverse=True))

    for root in search_roots:
        try:
            root_info = root.stat(follow_symlinks=False)
        except FileNotFoundError:
            continue
        except OSError as exc:
            add_entry({'source_path': str(root), 'status': 'ERROR', 'error': str(exc)})
            continue
        if stat.S_ISLNK(root_info.st_mode):
            add_entry({'source_path': str(root), 'status': 'ERROR',
                            'error': 'symlinked collection root is not allowed'})
            continue
        identities = {root: _file_identity(root_info)}
        for directory, files in walk(root, identities):
            if 'SKILL.md' not in files:
                continue
            if len(entries) >= _MAX_SCAN_SKILLS:
                raise ValueError('installed collection exceeds scan entry limit')
            path = Path(directory) / 'SKILL.md'
            entry = {'source_path': str(path)}
            try:
                if path.is_symlink() or not path.is_file():
                    raise ValueError('SKILL.md must be a regular non-symlink file')
                size = path.stat().st_size
                if size > 1_000_000:
                    raise ValueError('SKILL.md exceeds 1MB')
                if bytes_seen + size > _MAX_COLLECTION_BYTES:
                    raise _CollectionLimitError('installed collection exceeds byte limit')
                bytes_seen += size
                ir = compile_skill_file(path, max_bytes=size, identities=identities)
                entry.update(status='ANALYZED',
                             skill_name=ir['skills'][0]['identity']['name'],
                             audit=audit_corpus(ir), ir=_redact_ir(ir))
            except _CollectionLimitError:
                raise
            except (ValueError, OSError, UnicodeError) as exc:
                entry.update(status='ERROR', error=str(exc))
            add_entry(entry)
    entries.sort(key=lambda entry: entry['source_path'])
    analyzed = sum(e['status'] == 'ANALYZED' for e in entries)
    status = 'EMPTY' if not entries else ('COMPLETE' if analyzed == len(entries) else 'PARTIAL')
    payload = {
        'schema_version': 'crucible-installed-collection/v2',
        'scope': 'independent-packages',
        'status': status,
        'entries': entries,
        'coverage': {
            'scope': 'independent-packages',
            'status': status,
            'discovered': len(entries),
            'analyzed': analyzed,
            'skipped': 0,
            'errors': len(entries) - analyzed,
            'searched': [str(p) for p in search_roots],
        },
        'limitations': ['Cross-package composition is not evaluated.'],
    }
    payload['collection_digest'] = digest_payload(payload)
    return payload


def _standard_skill_dirs() -> list[Path]:
    """Return the standard skill directories for the current user."""
    home = Path.home()
    return [
        home / ".config" / "devin" / "skills",
        home / ".claude" / "skills",
        home / ".local" / "share" / "devin" / "skills",
        home / ".codex" / "skills",
    ]


def _normalize_explicit_roots(
    roots: Sequence[str | os.PathLike[str]],
) -> list[Path]:
    """Validate caller-selected local scan roots without following symlinks."""
    if isinstance(roots, (str, bytes, os.PathLike)) or not isinstance(roots, Sequence):
        raise ValueError('explicit scan roots must be a sequence of directory paths')
    if not roots:
        raise ValueError('explicit scan roots must not be empty')
    if len(roots) > _MAX_EXPLICIT_SCAN_ROOTS:
        raise ValueError('explicit scan root limit exceeded')

    normalized: list[Path] = []
    seen: set[Path] = set()
    for value in roots:
        if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
            raise ValueError('explicit scan root must be a non-empty path')
        candidate = Path(value).expanduser()
        candidate = Path(os.path.abspath(candidate))
        try:
            info = candidate.stat(follow_symlinks=False)
        except OSError as exc:
            raise ValueError(f'explicit scan root is unavailable: {candidate}') from exc
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f'explicit scan root must not be a symlink: {candidate}')
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError(f'explicit scan root must be a directory: {candidate}')
        if candidate in seen:
            raise ValueError(f'explicit scan root is duplicated: {candidate}')
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def _find_installed_skill_dirs() -> list[Path]:
    """Find which standard skill directories exist and contain skills."""
    found = []
    for d in _standard_skill_dirs():
        if d.is_dir():
            found.append(d)
    return found


def _validate_skill_text(skill_text: str) -> None:
    """Validate the skill text at the boundary."""
    if not isinstance(skill_text, str):
        raise ValueError("skill_text must be a string")
    if not skill_text.strip():
        raise ValueError("skill_text must not be empty")
    if len(skill_text) > 1_000_000:
        raise ValueError("skill_text must not exceed 1MB")


def _sanitize_skill_name(skill_name: str) -> str:
    """Sanitize a user-supplied skill name to prevent path traversal (RT-01).

    Rejects names containing path separators, .. components, or empty
    strings. Returns the sanitized name if safe, raises ValueError
    otherwise.
    """
    if not isinstance(skill_name, str):
        raise ValueError("skill_name must be a string")
    if not skill_name.strip():
        raise ValueError("skill_name must not be empty")
    if len(skill_name) > 200:
        raise ValueError("skill_name must not exceed 200 characters")
    # Reject path separators and traversal attempts.
    if "/" in skill_name or "\\" in skill_name:
        raise ValueError("skill_name must not contain path separators")
    if skill_name in (".", ".."):
        raise ValueError("skill_name must not be a path traversal component")
    # Reject names that resolve to a parent path.
    from pathlib import PurePosixPath
    parts = PurePosixPath(skill_name).parts
    if any(p == ".." for p in parts):
        raise ValueError("skill_name must not contain '..' components")
    return skill_name


# Maximum number of skills to scan in directory/installed mode (RT-04).
_MAX_SCAN_SKILLS = 500


def _redact_ir(ir: dict[str, Any]) -> dict[str, Any]:
    """Redact the L1 IR for API responses (RT-03).

    Removes body_text from each skill to prevent information disclosure.
    The audit and graph artifacts are safe to return — they contain
    findings and structural metadata, not raw file content.
    """
    redacted = dict(ir)
    redacted_skills = []
    for skill in ir.get("skills", []):
        redacted_skill = dict(skill)
        redacted_skill.pop("body_text", None)
        redacted_skills.append(redacted_skill)
    redacted["skills"] = redacted_skills
    # Recompute the digest over the redacted IR so consumers can verify
    # integrity without receiving the raw content.
    from .ir import digest_payload
    redacted["artifact_digest"] = digest_payload({
        "schema_version": redacted.get("schema_version"),
        "skills": redacted_skills,
    })
    return redacted


def _validate_directory(directory: str) -> None:
    """Validate the directory path at the boundary."""
    if not isinstance(directory, str):
        raise ValueError("directory must be a string")
    if not directory.strip():
        raise ValueError("directory must not be empty")
    path = Path(directory).resolve()
    if not path.is_dir():
        raise ValueError(f"directory does not exist: {directory}")
    # compile_corpus performs bounded recursive discovery and rejects an
    # empty corpus. A shallow precheck here would reject nested repositories.


def create_app() -> Any:
    """Create the FastAPI application.

    This is a factory function so the app can be created on demand and
    tested without a running server.
    """
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel

    app = FastAPI(
        title="Crucible Skill Scanner",
        description="Scan third-party SKILL.md files for engineering defects.",
        version="0.1.0",
    )

    class ScanSkillRequest(BaseModel):
        skill_text: str
        skill_name: str = "uploaded"

    class ScanDirectoryRequest(BaseModel):
        directory: str

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    def _refused(exc: Exception) -> HTTPException:
        """Turn a refusal into a 400 the caller can act on.

        The reader walks a real filesystem, so an unreadable entry anywhere
        under the given root raises OSError, not ValueError. Catching only
        ValueError turned an ordinary unreadable subdirectory -- /tmp holds
        systemd-private-* dirs the server cannot enter -- into an unhandled
        500 with no message. The CLI already caught both for the same calls.
        """
        if isinstance(exc, OSError):
            target = getattr(exc, "filename", None)
            where = f" at {target}" if target else ""
            return HTTPException(
                status_code=400,
                detail=f"could not read the corpus{where}: {exc.strerror or exc}",
            )
        return HTTPException(status_code=400, detail=str(exc))

    @app.post("/scan/skill")
    def scan_skill(req: ScanSkillRequest) -> JSONResponse:
        try:
            result = scan_skill_text(req.skill_text, req.skill_name)
        except (ValueError, OSError) as exc:
            raise _refused(exc)
        return JSONResponse(content=result)

    @app.post("/scan/directory")
    def scan_dir(req: ScanDirectoryRequest) -> JSONResponse:
        try:
            result = scan_directory(req.directory)
        except (ValueError, OSError) as exc:
            raise _refused(exc)
        return JSONResponse(content=result)

    @app.get("/scan/installed")
    def scan_installed() -> JSONResponse:
        try:
            result = scan_installed_skills()
        except (ValueError, OSError) as exc:
            raise _refused(exc)
        return JSONResponse(content=result)

    @app.post("/report/skill")
    def report_skill(req: ScanSkillRequest) -> JSONResponse:
        try:
            result = report_skill_text(req.skill_text, req.skill_name)
        except (ValueError, OSError) as exc:
            raise _refused(exc)
        return JSONResponse(content=result)

    @app.post("/report/directory")
    def report_dir(req: ScanDirectoryRequest) -> JSONResponse:
        try:
            result = report_directory(req.directory)
        except (ValueError, OSError) as exc:
            raise _refused(exc)
        return JSONResponse(content=result)

    @app.get("/report/installed")
    def report_inst() -> JSONResponse:
        try:
            result = report_installed()
        except (ValueError, OSError) as exc:
            raise _refused(exc)
        return JSONResponse(content=result)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _demo_html()

    return app


def _demo_html() -> str:
    """Return the demo UI HTML page.

    The UI is read-only: it calls the API and renders the results. No
    computation happens in the browser beyond fetching and displaying.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crucible Skill Scanner</title>
<style>
/* Shared palette with remember-the-seasons (same hackathon). Every text role
   here clears WCAG AA against --bg: text 16.5:1, --dim 7.1:1, --g 8.0:1,
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
.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tab { padding: 8px 16px; background: var(--p2); color: var(--dim); border: 1px solid var(--line); border-radius: 4px; cursor: pointer; font-size: 14px; }
.tab:hover { color: var(--tx); border-color: var(--g-dim); }
.tab.active { background: var(--g); color: var(--bg); border-color: var(--g); font-weight: 600; }
.panel { display: none; }
.panel.active { display: block; }
textarea, input[type="text"] { width: 100%; box-sizing: border-box; padding: 12px; background: var(--p2); color: var(--tx); border: 1px solid var(--line); border-radius: 4px; font-family: var(--mono); font-size: 13px; }
textarea { min-height: 200px; }
textarea:focus, input[type="text"]:focus { outline: 2px solid var(--g); outline-offset: 1px; border-color: var(--g); }
button { padding: 10px 20px; background: var(--g); color: var(--bg); border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: 600; margin-top: 8px; }
button:hover { background: var(--g-dim); }
button:focus-visible { outline: 2px solid var(--tx); outline-offset: 2px; }
button:disabled { background: var(--line); color: var(--dim); cursor: not-allowed; }
button.secondary { background: transparent; color: var(--g); border: 1px solid var(--g); margin-left: 8px; }
button.secondary:hover { background: var(--g-dim); color: var(--bg); }
.report-note { color: var(--dim); font-size: 13px; margin: 0 0 8px; }
.report-frame { width: 100%; height: 75vh; border: 1px solid var(--line); border-radius: 4px; background: #fff; }
.result { margin-top: 24px; }
.digest { font-family: var(--mono); font-size: 12px; color: var(--dim); word-break: break-all; background: var(--p2); border: 1px solid var(--line2); padding: 8px; border-radius: 4px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { text-align: left; padding: 8px 12px; border: 1px solid var(--line); vertical-align: top; }
th { background: var(--p2); font-weight: 600; color: var(--dim); }
code { font-family: var(--mono); color: var(--dim); }
.finding { margin: 8px 0; padding: 12px; border-left: 4px solid var(--bad); background: var(--p2); border-radius: 4px; }
.finding.candidate { border-left-color: var(--warn); }
.finding.observation { border-left-color: var(--dim); }
.finding-class { font-weight: bold; color: var(--tx); }
.finding-evidence { color: var(--dim); margin-top: 4px; }
.finding-skill { color: var(--dim); font-size: 13px; }
.summary { display: flex; gap: 16px; margin: 16px 0; }
.summary-card { padding: 16px; background: var(--p2); border: 1px solid var(--line2); border-radius: 6px; flex: 1; }
.summary-number { font-size: 28px; font-weight: bold; color: var(--g); }
.summary-label { font-size: 13px; color: var(--dim); }
.note { color: var(--dim); font-size: 13px; margin: 4px 0 12px; }
.outcome-abstained { color: var(--warn); font-weight: bold; }
.outcome-exercised { color: var(--g); }
.cov-complete { color: var(--g); }
.cov-partial { color: var(--warn); }
/* The abstention reasons are full sentences; without fixed proportions the
   reason column collapses to a sliver while short columns keep the width. */
table.preconditions { table-layout: fixed; }
table.preconditions th:nth-child(1), table.preconditions td:nth-child(1) { width: 20%; overflow-wrap: break-word; }
table.preconditions th:nth-child(2), table.preconditions td:nth-child(2) { width: 9%; }
table.preconditions th:nth-child(3), table.preconditions td:nth-child(3) { width: 17%; }
table.preconditions th:nth-child(4), table.preconditions td:nth-child(4) { width: 7%; text-align: right; }
table.preconditions th:nth-child(5), table.preconditions td:nth-child(5) { width: 47%; }
table.preconditions code { font-size: 11px; word-break: break-word; }
.error { color: var(--bad); background: var(--p2); border: 1px solid var(--bad); padding: 12px; border-radius: 4px; }
.loading { color: var(--dim); font-style: italic; }
.error-hint { color: var(--dim); font-size: 13px; margin-top: 6px; }
.field-error { color: var(--bad); font-size: 13px; margin: 6px 0 0; min-height: 1em; }
[aria-invalid="true"] { border-color: var(--bad); }
.empty-state { color: var(--dim); background: var(--p2); border: 1px solid var(--line2); padding: 16px; border-radius: 6px; }
</style>
</head>
<body>
<div class="container">
<h1>Crucible Skill Scanner</h1>
<p>Scan third-party SKILL.md files for engineering defects. Deterministic, evidence-backed, sealed.</p>

<div class="tabs">
<button class="tab active" role="tab" data-tab="skill" aria-selected="true" onclick="showTab('skill')">Single Skill</button>
<button class="tab" role="tab" data-tab="directory" aria-selected="false" onclick="showTab('directory')">Directory</button>
<button class="tab" role="tab" data-tab="installed" aria-selected="false" onclick="showTab('installed')">Installed Skills</button>
</div>

<div id="skill" class="panel active">
<h2>Paste a SKILL.md</h2>
<textarea id="skill-text" placeholder="---&#10;name: my-skill&#10;description: ...&#10;---&#10;&#10;# Instructions&#10;..."></textarea>
<br>
<input type="text" id="skill-name" placeholder="skill name (optional)" value="uploaded">
<p class="field-error" id="skill-text-error" role="alert"></p>
<br>
<button data-scan onclick="scanSkill()">Scan</button>
<button data-scan class="secondary" onclick="reportSkill()">Report (no model)</button>
</div>

<div id="directory" class="panel">
<h2>Scan a Directory</h2>
<input type="text" id="directory-path" placeholder="/path/to/skills/directory">
<p class="field-error" id="directory-path-error" role="alert"></p>
<br>
<button data-scan onclick="scanDirectory()">Scan</button>
<button data-scan class="secondary" onclick="reportDirectory()">Report (no model)</button>
</div>

<div id="installed" class="panel">
<h2>Scan Installed Skills</h2>
<p>Scans ~/.config/devin/skills/, ~/.claude/skills/, and ~/.local/share/devin/skills/.</p>
<button data-scan onclick="scanInstalled()">Scan</button>
<button data-scan class="secondary" onclick="reportInstalled()">Report (no model)</button>
</div>

<div id="result" class="result" aria-live="polite" aria-busy="false"></div>
</div>

<script>
// Derives the tab from its id rather than the implicit global `event`, which
// is deprecated and left showTab unusable from anything but a click handler.
function showTab(tabId) {
  document.querySelectorAll('.tab').forEach(t => {
    const on = t.getAttribute('data-tab') === tabId;
    t.classList.toggle('active', on);
    t.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById(tabId).classList.add('active');
}

let pendingScan = 0;

// Every scan goes through this, so the four states (busy, error, empty,
// success) are reachable from one place instead of each caller inventing one.
async function runScan(label, request, render = renderResult) {
  const token = ++pendingScan;
  setBusy(true, label);
  let resp;
  try {
    resp = await request();
  } catch (e) {
    if (token !== pendingScan) { return; }
    setBusy(false);
    renderError('Could not reach the Crucible API.',
                'The server may have stopped. It runs locally: check the ' +
                'terminal running `crucible --serve`, then try again.');
    return;
  }
  let data = null;
  try { data = await resp.json(); } catch (e) { data = null; }
  if (token !== pendingScan) { return; }  // a newer scan already started
  setBusy(false);
  if (!resp.ok) {
    renderError(describeDetail(data, resp.status), hintForStatus(resp.status));
    return;
  }
  if (!data) { renderError('The server returned a response that is not JSON.', ''); return; }
  render(data);
}

function scanSkill() {
  const text = document.getElementById('skill-text').value;
  const name = document.getElementById('skill-name').value || 'uploaded';
  if (!requireValue(text, 'skill-text', 'Paste a SKILL.md first.')) { return; }
  return runScan('Compiling and auditing the skill', () => fetch('/scan/skill', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({skill_text: text, skill_name: name})
  }));
}

function scanDirectory() {
  const path = document.getElementById('directory-path').value;
  if (!requireValue(path, 'directory-path', 'Enter a directory path first.')) { return; }
  return runScan('Reading and auditing the directory', () => fetch('/scan/directory', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({directory: path})
  }));
}

function scanInstalled() {
  return runScan('Scanning installed skills', () => fetch('/scan/installed'));
}

// The report endpoints return the sealed report and its own HTML rendering.
// It is shown in a sandboxed frame (no scripts, no same-origin access), so the
// skill text it quotes can never run in this page.
function renderReport(data) {
  const result = document.getElementById('result');
  result.innerHTML = '';
  const note = document.createElement('p');
  note.className = 'report-note';
  note.textContent = 'Deterministic report: no model was called, so candidate findings stay ' +
    'unconfirmed and nothing is narrated. Report digest: ' + data.report.report_digest;
  const frame = document.createElement('iframe');
  frame.className = 'report-frame';
  frame.setAttribute('sandbox', '');
  frame.setAttribute('title', 'Crucible report');
  frame.srcdoc = data.html;
  result.append(note, frame);
}

function reportSkill() {
  const text = document.getElementById('skill-text').value;
  const name = document.getElementById('skill-name').value || 'uploaded';
  if (!requireValue(text, 'skill-text', 'Paste a SKILL.md first.')) { return; }
  return runScan('Building the report', () => fetch('/report/skill', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({skill_text: text, skill_name: name})
  }), renderReport);
}

function reportDirectory() {
  const path = document.getElementById('directory-path').value;
  if (!requireValue(path, 'directory-path', 'Enter a directory path first.')) { return; }
  return runScan('Building the report', () => fetch('/report/directory', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({directory: path})
  }), renderReport);
}

function reportInstalled() {
  return runScan('Building the report', () => fetch('/report/installed'), renderReport);
}

// Inline validation. A modal alert blocks the page and says nothing the field
// itself could not say next to the input.
function requireValue(value, fieldId, message) {
  const field = document.getElementById(fieldId);
  const slot = document.getElementById(fieldId + '-error');
  if (value && value.trim()) {
    if (slot) { slot.textContent = ''; }
    field.removeAttribute('aria-invalid');
    return true;
  }
  if (slot) { slot.textContent = message; }
  field.setAttribute('aria-invalid', 'true');
  field.focus();
  return false;
}

function setBusy(busy, label) {
  document.querySelectorAll('button[data-scan]').forEach(b => { b.disabled = busy; });
  const result = document.getElementById('result');
  result.setAttribute('aria-busy', busy ? 'true' : 'false');
  if (busy) {
    result.innerHTML = '<p class="loading">' + escapeHtml(label || 'Scanning') +
      '\u2026 nothing leaves this machine; no model is called.</p>';
  }
}

// FastAPI returns `detail` as a string for HTTPException and as a list of
// objects for a 422 validation error. Rendering the list directly printed
// "[object Object]".
function describeDetail(data, status) {
  const detail = data && data.detail !== undefined ? data.detail : (data && data.error);
  if (typeof detail === 'string' && detail) { return detail; }
  if (Array.isArray(detail)) {
    return detail.map(d => {
      const where = Array.isArray(d.loc) ? d.loc.join('.') : '';
      return (where ? where + ': ' : '') + (d.msg || JSON.stringify(d));
    }).join('; ');
  }
  if (detail && typeof detail === 'object') { return JSON.stringify(detail); }
  return 'The server returned HTTP ' + status + ' with no message.';
}

function hintForStatus(status) {
  if (status === 400) { return 'Check the path exists and holds at least one SKILL.md.'; }
  if (status === 404) { return 'That endpoint is not served by this build.'; }
  if (status === 413 || status === 422) { return 'The request was rejected before any analysis ran.'; }
  if (status >= 500) { return 'The failure is on the server side; its terminal has the traceback.'; }
  return '';
}

function renderError(message, hint) {
  let html = '<div class="error" role="alert"><strong>Scan failed.</strong> ' + escapeHtml(message);
  if (hint) { html += '<div class="error-hint">' + escapeHtml(hint) + '</div>'; }
  html += '</div>';
  document.getElementById('result').innerHTML = html;
}

function renderResult(data) {
  if (data.error) { renderError(data.error); return; }
  const audit = data.audit;
  if (!audit) { renderError('No audit returned'); return; }
  const findings = audit.findings || [];
  const byClass = {};
  findings.forEach(f => { byClass[f.class] = (byClass[f.class] || 0) + 1; });
  const skillCount = data.ir ? data.ir.skills.length : 0;
  if (skillCount === 0) {
    // Zero skills analyzed is not a clean result; it means nothing was read.
    document.getElementById('result').innerHTML =
      '<div class="empty-state"><strong>No skills were analyzed.</strong> ' +
      'Nothing was read, so this is not a statement about quality. ' +
      'Check that the path holds at least one SKILL.md file.' +
      renderCoverage(data.coverage) + '</div>';
    return;
  }
  let html = '<div class="summary">';
  html += '<div class="summary-card"><div class="summary-number">' + skillCount + '</div><div class="summary-label">Skills Scanned</div></div>';
  html += '<div class="summary-card"><div class="summary-number">' + findings.length + '</div><div class="summary-label">Findings</div></div>';
  html += '<div class="summary-card"><div class="summary-number">' + Object.keys(byClass).length + '</div><div class="summary-label">Defect Classes</div></div>';
  html += '</div>';
  html += '<div class="digest">Audit digest: ' + escapeHtml(audit.audit_digest || '') + '</div>';
  html += renderCoverage(data.coverage);
  html += renderExcluded(data.ir ? data.ir.excluded : null);
  html += '<h2>Findings</h2>';
  if (findings.length === 0) {
    // "passed every check" was the claim here, and it was false: a check that
    // abstained because this corpus gave it no input did not pass anything.
    const abstained = abstainedChecks(audit);
    html += '<p>No findings were emitted.';
    if (abstained.length) {
      html += ' ' + abstained.length + ' check(s) abstained on this input, so this is not evidence that the skill is clean.';
    }
    html += '</p>';
  } else {
    findings.forEach(f => {
      const cls = (f.epistemic_status || '').toLowerCase();
      html += '<div class="finding ' + cls + '">';
      html += '<div class="finding-class">' + escapeHtml(f.class || '') + '</div>';
      html += '<div class="finding-skill">Skill: ' + escapeHtml(f.skill || '') + ' | Status: ' + escapeHtml(f.epistemic_status || '') + '</div>';
      html += '<div class="finding-evidence">' + escapeHtml(f.evidence || '') + '</div>';
      if (f.violated_invariant) { html += '<div class="finding-evidence">Invariant: ' + escapeHtml(f.violated_invariant) + '</div>'; }
      html += '</div>';
    });
  }
  html += renderPreconditions(audit);
  document.getElementById('result').innerHTML = html;
}

function abstainedChecks(audit) {
  const pre = audit.preconditions || {};
  return (pre.checks || []).filter(c => c.outcome === 'ABSTAINED');
}

function renderPreconditions(audit) {
  const pre = audit.preconditions || {};
  const checks = pre.checks || [];
  if (!checks.length) { return ''; }
  const abstained = checks.filter(c => c.outcome === 'ABSTAINED');
  let html = '<h2>Check preconditions &mdash; ' + abstained.length + ' abstained</h2>';
  if (pre.limitation) { html += '<p class="note">' + escapeHtml(pre.limitation) + '</p>'; }
  html += '<table class="preconditions"><tr><th>Check</th><th>Outcome</th><th>Requires</th><th>Observed</th><th>Why it abstained</th></tr>';
  checks.slice().sort((a, b) => (a.outcome === 'ABSTAINED' ? 0 : 1) - (b.outcome === 'ABSTAINED' ? 0 : 1)
      || String(a.check_class).localeCompare(String(b.check_class))).forEach(c => {
    const css = c.outcome === 'ABSTAINED' ? 'outcome-abstained' : 'outcome-exercised';
    html += '<tr><td>' + escapeHtml(c.check_class || '').split('_').join('_<wbr>') + '</td>';
    html += '<td class="' + css + '">' + escapeHtml(c.outcome || '') + '</td>';
    html += '<td><code>' + escapeHtml(c.requires || '') + '</code></td>';
    html += '<td>' + escapeHtml(String(c.observed)) + '</td>';
    html += '<td>' + escapeHtml(c.reason || '') + '</td></tr>';
  });
  html += '</table>';
  return html;
}

function renderCoverage(coverage) {
  if (!coverage || !coverage.status) { return ''; }
  const complete = coverage.status === 'COMPLETE';
  let html = '<h2>Scan coverage &mdash; <span class="' + (complete ? 'cov-complete' : 'cov-partial') + '">' + escapeHtml(coverage.status) + '</span></h2>';
  html += '<table><tr><th>discovered</th><th>analyzed</th><th>skipped</th><th>errors</th></tr><tr>';
  ['discovered', 'analyzed', 'skipped', 'errors'].forEach(k => {
    html += '<td>' + escapeHtml(String(coverage[k] === undefined ? '-' : coverage[k])) + '</td>';
  });
  html += '</tr></table>';
  if (!complete) { html += '<p class="note">Partial coverage. Findings describe the analyzed subset only.</p>'; }
  return html;
}

function renderExcluded(excluded) {
  if (!Array.isArray(excluded) || !excluded.length) { return ''; }
  const lost = excluded.filter(e => e.reason === 'DUPLICATE_NAME_DISTINCT_CONTENT').length;
  let html = '<h2>Excluded skills &mdash; ' + excluded.length + '</h2>';
  html += '<p class="note">' + lost + ' of ' + excluded.length + ' dropped a distinct methodology sharing a name with one that was kept; the rest were byte-identical republications.</p>';
  html += '<table><tr><th>Name</th><th>Dropped</th><th>Kept</th><th>Reason</th></tr>';
  excluded.forEach(e => {
    html += '<tr><td>' + escapeHtml(e.name || '') + '</td>';
    html += '<td><code>' + escapeHtml(e.source_path || '') + '</code></td>';
    html += '<td><code>' + escapeHtml(e.kept_source_path || '') + '</code></td>';
    html += '<td>' + escapeHtml(e.reason || '') + '</td></tr>';
  });
  html += '</table>';
  return html;
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
</script>
</body>
</html>"""

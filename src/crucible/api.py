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
from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Sequence

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


def scan_skill_text(skill_text: str, skill_name: str = "uploaded") -> dict[str, Any]:
    """Compile and audit a single SKILL.md provided as text.

    The skill is written to a temporary directory, compiled, audited, and
    the temporary directory is removed. No input is retained.

    Returns the audit artifact (crucible-audit/v1) with the L3 graph.
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


def scan_installed_skills(
    roots: Iterable[str | os.PathLike[str]] | None = None,
) -> dict[str, Any]:
    """Scan the user's installed skills.

    Searches the standard skill directories:
    - ~/.config/devin/skills/
    - ~/.claude/skills/
    - ~/.local/share/devin/skills/
    - ~/.codex/skills/ (direct child skill packages)

    Returns the audit artifact with the L1 IR and L3 graph.
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
        return {
            "audit": None,
            "ir": None,
            "graph": None,
            "error": "no installed skills found in standard directories",
            "skipped_duplicates": [],
            "searched": [str(p) for p in search_roots],
            "coverage": coverage_report([], 0),
        }
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
            return {
                "audit": None,
                "ir": None,
                "graph": None,
                "error": "no SKILL.md files found in installed skill directories",
                "skipped_duplicates": skipped_duplicates,
                "searched": [str(p) for p in skill_dirs],
                "coverage": coverage_report(coverage_items, count),
            }
        ir = compile_corpus(tmpdir, max_skills=_MAX_SCAN_SKILLS)
        audit = audit_corpus(ir)
        graph = build_composition_graph(ir, audit)
        return {
            "audit": audit,
            "ir": _redact_ir(ir),
            "graph": graph,
            "skipped_duplicates": skipped_duplicates,
            "coverage": coverage_report(coverage_items, count),
        }


def scan_installed_collection() -> dict[str, Any]:
    """Audit nested packages independently; names need not be globally unique.

    Directory symlinks are recorded but never followed. Per-package errors
    remain in coverage; this mode makes no cross-package composition claim.
    """
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

    for root in _standard_skill_dirs():
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
    payload = {
        'schema_version': 'crucible-installed-collection/v1',
        'scope': 'independent-packages',
        'status': 'EMPTY' if not entries else ('COMPLETE' if analyzed == len(entries) else 'PARTIAL'),
        'entries': entries,
        'coverage': {'discovered': len(entries), 'analyzed': analyzed,
                     'errors': len(entries) - analyzed},
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

    @app.post("/scan/skill")
    def scan_skill(req: ScanSkillRequest) -> JSONResponse:
        try:
            result = scan_skill_text(req.skill_text, req.skill_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return JSONResponse(content=result)

    @app.post("/scan/directory")
    def scan_dir(req: ScanDirectoryRequest) -> JSONResponse:
        try:
            result = scan_directory(req.directory)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return JSONResponse(content=result)

    @app.get("/scan/installed")
    def scan_installed() -> JSONResponse:
        result = scan_installed_skills()
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
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #f5f5f5; color: #222; }
.container { max-width: 960px; margin: 0 auto; background: #fff; padding: 40px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
h1 { margin-top: 0; color: #1a1a2e; }
h2 { margin-top: 32px; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; color: #1a1a2e; }
.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tab { padding: 8px 16px; background: #e0e0e0; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
.tab.active { background: #1a1a2e; color: #fff; }
.panel { display: none; }
.panel.active { display: block; }
textarea { width: 100%; min-height: 200px; padding: 12px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; font-size: 13px; }
input[type="text"] { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
button { padding: 10px 20px; background: #1a1a2e; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; margin-top: 8px; }
button:hover { background: #2a2a4e; }
button:disabled { background: #999; cursor: not-allowed; }
.result { margin-top: 24px; }
.digest { font-size: 12px; color: #555; word-break: break-all; background: #f0f0f0; padding: 8px; border-radius: 4px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { text-align: left; padding: 8px 12px; border: 1px solid #ddd; vertical-align: top; }
th { background: #f8f8f8; font-weight: 600; }
.finding { margin: 8px 0; padding: 12px; border-left: 4px solid #dc3545; background: #f8f8f8; border-radius: 4px; }
.finding.candidate { border-left-color: #ffc107; }
.finding.observation { border-left-color: #17a2b8; }
.finding-class { font-weight: bold; color: #1a1a2e; }
.finding-evidence { color: #555; margin-top: 4px; }
.finding-skill { color: #777; font-size: 13px; }
.summary { display: flex; gap: 16px; margin: 16px 0; }
.summary-card { padding: 16px; background: #f8f8f8; border-radius: 6px; flex: 1; }
.summary-number { font-size: 28px; font-weight: bold; color: #1a1a2e; }
.summary-label { font-size: 13px; color: #666; }
.error { color: #721c24; background: #f8d7da; padding: 12px; border-radius: 4px; }
.loading { color: #666; font-style: italic; }
</style>
</head>
<body>
<div class="container">
<h1>Crucible Skill Scanner</h1>
<p>Scan third-party SKILL.md files for engineering defects. Deterministic, evidence-backed, sealed.</p>

<div class="tabs">
<button class="tab active" onclick="showTab('skill')">Single Skill</button>
<button class="tab" onclick="showTab('directory')">Directory</button>
<button class="tab" onclick="showTab('installed')">Installed Skills</button>
</div>

<div id="skill" class="panel active">
<h2>Paste a SKILL.md</h2>
<textarea id="skill-text" placeholder="---&#10;name: my-skill&#10;description: ...&#10;---&#10;&#10;# Instructions&#10;..."></textarea>
<br>
<input type="text" id="skill-name" placeholder="skill name (optional)" value="uploaded">
<br>
<button onclick="scanSkill()">Scan</button>
</div>

<div id="directory" class="panel">
<h2>Scan a Directory</h2>
<input type="text" id="directory-path" placeholder="/path/to/skills/directory">
<br>
<button onclick="scanDirectory()">Scan</button>
</div>

<div id="installed" class="panel">
<h2>Scan Installed Skills</h2>
<p>Scans ~/.config/devin/skills/, ~/.claude/skills/, and ~/.local/share/devin/skills/.</p>
<button onclick="scanInstalled()">Scan</button>
</div>

<div id="result" class="result"></div>
</div>

<script>
function showTab(tabId) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById(tabId).classList.add('active');
}

async function scanSkill() {
  const text = document.getElementById('skill-text').value;
  const name = document.getElementById('skill-name').value || 'uploaded';
  if (!text.trim()) { alert('Paste a SKILL.md first'); return; }
  showLoading();
  try {
    const resp = await fetch('/scan/skill', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({skill_text: text, skill_name: name})
    });
    const data = await resp.json();
    if (resp.ok) { renderResult(data); } else { renderError(data.detail || 'Unknown error'); }
  } catch (e) { renderError(e.message); }
}

async function scanDirectory() {
  const path = document.getElementById('directory-path').value;
  if (!path.trim()) { alert('Enter a directory path'); return; }
  showLoading();
  try {
    const resp = await fetch('/scan/directory', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({directory: path})
    });
    const data = await resp.json();
    if (resp.ok) { renderResult(data); } else { renderError(data.detail || 'Unknown error'); }
  } catch (e) { renderError(e.message); }
}

async function scanInstalled() {
  showLoading();
  try {
    const resp = await fetch('/scan/installed');
    const data = await resp.json();
    if (resp.ok) { renderResult(data); } else { renderError(data.detail || 'Unknown error'); }
  } catch (e) { renderError(e.message); }
}

function showLoading() {
  document.getElementById('result').innerHTML = '<p class="loading">Scanning...</p>';
}

function renderError(msg) {
  document.getElementById('result').innerHTML = '<div class="error">' + escapeHtml(msg) + '</div>';
}

function renderResult(data) {
  if (data.error) { renderError(data.error); return; }
  const audit = data.audit;
  if (!audit) { renderError('No audit returned'); return; }
  const findings = audit.findings || [];
  const byClass = {};
  findings.forEach(f => { byClass[f.class] = (byClass[f.class] || 0) + 1; });
  const skillCount = data.ir ? data.ir.skills.length : 0;
  let html = '<div class="summary">';
  html += '<div class="summary-card"><div class="summary-number">' + skillCount + '</div><div class="summary-label">Skills Scanned</div></div>';
  html += '<div class="summary-card"><div class="summary-number">' + findings.length + '</div><div class="summary-label">Findings</div></div>';
  html += '<div class="summary-card"><div class="summary-number">' + Object.keys(byClass).length + '</div><div class="summary-label">Defect Classes</div></div>';
  html += '</div>';
  html += '<div class="digest">Audit digest: ' + escapeHtml(audit.audit_digest || '') + '</div>';
  html += '<h2>Findings</h2>';
  if (findings.length === 0) {
    html += '<p>No findings. The skill(s) passed all 28 checks.</p>';
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
  document.getElementById('result').innerHTML = html;
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
</script>
</body>
</html>"""

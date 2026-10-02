"""Compile SKILL.md files into a deterministic, source-addressable IR."""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml

from .ir import SCHEMA_VERSION, digest_bytes, digest_payload

_MAX_CORPUS_BYTES = 20_000_000
_MAX_CORPUS_DIRECTORIES = 10_000
_MAX_CORPUS_ENTRIES = 100_000

# Match "MUST NOT" / "SHOULD NOT" (with space) before bare MUST/SHOULD/MAY
# so that negated modalities are captured correctly.
_MODALITY = re.compile(r"\b(MUST\s+NOT|SHOULD\s+NOT|MUST|SHOULD|MAY)\b")
_URL = re.compile(r"https?://[^\s)>]+")
_HEADING = re.compile(r"^(#{1,6})\s+(?P<title>.+?)\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+(?P<value>.+?)\s*$")
_NUMBERED = re.compile(r"^\s*(?P<num>\d+)\.\s+(?P<value>.+?)\s*$")
_PROCEDURAL_SECTIONS = {"steps", "procedure", "how to", "how", "process", "workflow", "method"}

# Code fence detection for skipping code blocks during extraction.
_CODE_FENCE = re.compile(r"^```")

# Normative imperative verbs — verbs that, when at the start of a line
# (after stripping markdown), indicate a normative constraint. These are
# NOT action verbs (read, write, create, build) which indicate procedural
# steps. They are constraint verbs: ensure, require, prevent, reject, etc.
_NORMATIVE_IMPERATIVE_VERBS = {
    "ensure", "require", "enforce", "maintain", "preserve", "protect",
    "guard", "isolate", "contain", "limit", "restrict", "constrain",
    "bound", "avoid", "prevent", "reject", "block", "deny", "abort",
    "rollback", "validate", "pin", "seal", "guarantee",
}

# Negative starters — lines that start with these words are normative
# rules (prohibitions or requirements). Each entry is (regex, modality).
_NORMATIVE_STARTERS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\s*(?:[-*+]\s+)?(?:\d+\.\s+)?never\b", re.IGNORECASE), "NEVER"),
    (re.compile(r"^\s*(?:[-*+]\s+)?(?:\d+\.\s+)?always\b", re.IGNORECASE), "ALWAYS"),
    (re.compile(r"^\s*(?:[-*+]\s+)?(?:\d+\.\s+)?do\s+not\b", re.IGNORECASE), "MUST_NOT"),
    (re.compile(r"^\s*(?:[-*+]\s+)?(?:\d+\.\s+)?don't\b", re.IGNORECASE), "MUST_NOT"),
]

# Imperative starter — lines that start with a normative verb.
_IMPERATIVE_STARTER = re.compile(
    r"^\s*(?:[-*+]\s+)?(?:\d+\.\s+)?"
    r"(?:" + "|".join(sorted(_NORMATIVE_IMPERATIVE_VERBS)) + r")\b",
    re.IGNORECASE,
)

# The single canonical list of verification/command verbs, shared by
# _VERIFICATION_STARTER (decides whether a line becomes a check at all)
# and _ORACLE_PATTERNS's "command" oracle_kind (decides, for a check that
# already exists, how it can be verified). ADR-0015 fixed this exact list
# as the canonical command-oracle vocabulary; _VERIFICATION_STARTER had
# drifted to an older, narrower 7-verb subset that predated that ADR and
# was never updated to match, so a line starting with "Run", "Query",
# "Inspect", "Does", "Ensure", or "Validate" -- each already accepted as a
# valid command-oracle verb -- could never become a check in the first
# place, regardless of how it would have been classified. Defining the
# list once here prevents the two from drifting apart again.
_VERIFICATION_VERBS = (
    "verify", "assert", "run", "check", "confirm", "test", "query",
    "inspect", "does", "ensure", "prove", "validate", "demonstrate",
)
_VERIFICATION_VERB_ALTERNATION = "|".join(_VERIFICATION_VERBS)

# Verification starter — lines that start with a verification verb.
# Used to extract checks from anywhere in the body, not just Checks sections.
_VERIFICATION_STARTER = re.compile(
    rf"^\s*(?:[-*+]\s+)?(?:\d+\.\s+)?(?:{_VERIFICATION_VERB_ALTERNATION})\b",
    re.IGNORECASE,
)

# Action verbs — first word of a bullet that indicates a procedural step
# (rather than an explanatory or descriptive bullet). These are concrete
# doing-words, distinct from the normative constraint verbs above. A
# bullet starting with one of these is treated as a prose-embedded step
# when it appears outside a dedicated procedural section.
_ACTION_VERBS = {
    "run", "execute", "build", "create", "generate", "write", "edit",
    "read", "load", "save", "delete", "remove", "install", "deploy",
    "start", "stop", "restart", "configure", "set", "update", "upgrade",
    "downgrade", "commit", "push", "pull", "merge", "rebase", "tag",
    "release", "publish", "scan", "audit", "inspect", "examine",
    "analyze", "review", "compare", "diff", "apply", "revert", "rollback",
    "validate", "verify", "check", "test", "assert", "confirm",
    "demonstrate", "prove", "extract", "compile", "parse", "serialize",
    "deserialize", "encode", "decode", "encrypt", "decrypt", "sign",
    "authenticate", "authorize", "grant", "revoke", "issue",
    "reset", "clear", "flush", "purge", "archive", "restore", "backup",
    "copy", "move", "rename", "list", "show", "print", "log", "report",
    "notify", "alert", "warn", "fail", "abort", "raise", "throw",
    "catch", "handle", "retry", "skip", "continue", "break", "return",
    "yield", "await", "call", "invoke", "trigger", "schedule", "queue",
    "fetch", "request", "send", "receive", "listen", "connect",
    "disconnect", "open", "close", "mount", "unmount", "format",
    "initialize", "teardown", "shutdown", "boot",
    "navigate", "select", "choose", "pick", "enter", "type", "paste",
    "click", "tap", "scroll", "zoom", "filter", "sort", "group",
    "aggregate", "summarize", "transform", "convert", "translate",
    "map", "reduce", "join", "split", "partition", "shard", "replicate",
    "cache", "invalidate", "refresh", "sync", "synchronize", "poll",
    "watch", "monitor", "observe", "measure", "record", "capture",
    "replay", "simulate", "emulate", "fuzz", "mutate", "patch", "fix",
    "repair", "refactor", "optimize", "profile", "benchmark", "trace",
    "debug", "dump", "export", "import", "upload", "download",
    "transfer", "stream", "pipe", "redirect", "forward", "route",
    "block", "allow", "deny", "accept", "reject", "drop", "pass",
    "enforce", "require", "ensure", "maintain", "preserve", "protect",
    "guard", "isolate", "contain", "limit", "restrict", "constrain",
    "bound", "avoid", "prevent", "pin", "seal", "guarantee",
}


class _TraversalBudget:
    """Mutable per-operation counters, optionally shared by multiple walks."""

    def __init__(self):
        self.entries = 0
        self.directories = 0

    def add_entry(self):
        self.entries += 1
        if self.entries > _MAX_CORPUS_ENTRIES:
            raise ValueError('corpus exceeds discovery entry limit')

    def add_directory(self):
        self.directories += 1
        if self.directories > _MAX_CORPUS_DIRECTORIES:
            raise ValueError('corpus exceeds directory limit')


def _file_identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _check_identity(fd: int, path: Path, identities: dict | None) -> None:
    if identities is not None and path in identities:
        if _file_identity(os.fstat(fd)) != identities[path]:
            raise ValueError(f'corpus identity changed: {path}')


@contextmanager
def _scan_corpus_directory(path: Path, *, identities: dict | None = None):
    """Enumerate a pinned directory, never reopening its pathname for scandir."""
    fd = _open_path_descriptor(path, directory=True, identities=identities)
    try:
        with os.scandir(fd) as children:
            yield children
    finally:
        os.close(fd)


def _discover_corpus(root: Path, max_skills: int | None,
                     *, identities: dict | None = None,
                     budget: _TraversalBudget | None = None) -> list[Path]:
    """Bound enumeration before sorting; propagate incomplete traversal errors."""
    if identities is None:
        identities = {}
    if root not in identities:
        identities[root] = _file_identity(root.stat(follow_symlinks=False))
    pending = [root]
    paths = []
    if budget is None:
        budget = _TraversalBudget()
    budget.add_directory()
    while pending:
        directory = pending.pop()
        with _scan_corpus_directory(directory, identities=identities) as children:
            for child in children:
                budget.add_entry()
                path = directory / child.name
                is_directory = child.is_dir(follow_symlinks=False)
                if child.name == 'SKILL.md' or is_directory:
                    identities[path] = _file_identity(child.stat(follow_symlinks=False))
                if child.name == 'SKILL.md':
                    paths.append(path)
                    if max_skills is not None and len(paths) > max_skills:
                        raise ValueError(
                            f'corpus contains at least {len(paths)} SKILL.md files, '
                            f'exceeding the limit of {max_skills}'
                        )
                if is_directory:
                    budget.add_directory()
                    pending.append(path)
    return sorted(paths, key=lambda p: p.relative_to(root).as_posix())


def compile_corpus(root: Path | str, max_skills: int | None = None) -> dict[str, Any]:
    """Compile every ``SKILL.md`` below *root* into a canonical artifact.

    If *max_skills* is set and the corpus contains more SKILL.md files
    than the limit, a ValueError is raised to prevent resource exhaustion
    (RT-04 fix). Discovery entries, directories and cumulative input bytes
    are bounded even when *max_skills* is None.
    """
    corpus_root = Path(root).resolve()
    if not corpus_root.is_dir():
        raise ValueError(f"corpus root is not a directory: {root}")

    identities: dict[Path, tuple[int, int]] = {}
    paths = _discover_corpus(corpus_root, max_skills, identities=identities)
    if not paths:
        raise ValueError(f"corpus contains no SKILL.md files: {root}")

    skills = []
    bytes_seen = 0
    for path in paths:
        if path.is_symlink():
            raise ValueError(f'{path.relative_to(corpus_root)}: symlinked SKILL.md is not allowed')
        raw_bytes = _read_skill_bytes(
            path, min(1_000_000, _MAX_CORPUS_BYTES - bytes_seen), identities=identities
        )
        bytes_seen += len(raw_bytes)
        skills.append(_compile_skill(path, corpus_root, raw_bytes=raw_bytes))
    names = [skill["identity"]["name"] for skill in skills]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"duplicate skill name(s): {', '.join(duplicates)}")

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "skills": skills,
    }
    payload["artifact_digest"] = digest_payload(payload)
    return payload


def _open_path_descriptor(path: Path, *, directory: bool = False,
                          identities: dict | None = None) -> int:
    """Pin each directory before opening the next component, refusing links."""
    import os
    if not all(hasattr(os, flag) for flag in ('O_NOFOLLOW', 'O_DIRECTORY', 'O_NONBLOCK')):
        raise ValueError('safe single-file reading is unsupported on this platform')
    absolute = path.absolute()
    if '..' in absolute.parts:
        raise ValueError('parent traversal is not allowed in single-file paths')
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
    directory_fd = os.open(absolute.anchor, flags)
    try:
        current = Path(absolute.anchor)
        _check_identity(directory_fd, current, identities)
        components = absolute.parts[1:] if directory else absolute.parts[1:-1]
        for component in components:
            next_fd = os.open(component, flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
            current = current / component
            _check_identity(directory_fd, current, identities)
        if directory:
            return os.dup(directory_fd)
        return os.open(absolute.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                       dir_fd=directory_fd)
    finally:
        os.close(directory_fd)


def compile_skill_file(path: Path | str, max_bytes: int = 1_000_000,
                       *, identities: dict | None = None) -> dict[str, Any]:
    """Compile exactly one entry point using the existing extraction rules."""
    path = Path(path)
    raw_bytes = _read_skill_bytes(path, max_bytes, identities=identities)
    skill = _compile_skill(path, path.parent, raw_bytes=raw_bytes)
    payload = {'schema_version': SCHEMA_VERSION, 'skills': [skill]}
    payload['artifact_digest'] = digest_payload(payload)
    return payload


def _read_skill_bytes(path: Path, max_bytes: int = 1_000_000,
                      *, identities: dict | None = None) -> bytes:
    """Capture bounded bytes from one regular file without reopening its path."""
    import os
    import stat
    fd = _open_path_descriptor(path, identities=identities)
    try:
        _check_identity(fd, path, identities)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('SKILL.md must be a regular file')
        if before.st_size > max_bytes:
            raise ValueError('SKILL.md exceeds read byte limit')
        chunks = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(remaining, 65536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)
        if remaining or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size, after.st_mtime_ns, after.st_ctime_ns
        ):
            raise ValueError('SKILL.md changed during reading')
        raw_bytes = b''.join(chunks)
    finally:
        os.close(fd)
    return raw_bytes


def _compile_skill(path: Path, root: Path, raw_bytes: bytes | None = None) -> dict[str, Any]:
    relative_path = path.relative_to(root).as_posix()
    if raw_bytes is None:
        if path.is_symlink():
            raise ValueError(f"{relative_path}: symlinked SKILL.md is not allowed")
        raw_bytes = _read_skill_bytes(path)
    raw = raw_bytes.decode("utf-8")
    lines = raw.splitlines()
    frontmatter, body_start = _parse_frontmatter(lines, relative_path)
    name = frontmatter.get("name")
    if not name:
        raise ValueError(f"{relative_path}: frontmatter requires name")
    if not frontmatter.get("description"):
        raise ValueError(f"{relative_path}: frontmatter requires description")

    sections = _section_ranges(lines, body_start)
    body_text = "\n".join(lines[body_start:])
    return {
        "identity": {
            "name": name,
            "source_path": relative_path,
            "content_digest": digest_bytes(raw_bytes),
        },
        "metadata": {key: frontmatter[key] for key in sorted(frontmatter)},
        "trigger": _extract_trigger(frontmatter.get("description", "")),
        "body_text": body_text,
        "rules": _extract_rules(lines, body_start),
        "checks": _extract_checks(lines, sections, body_start),
        "procedural_steps": _extract_procedural_steps(lines, sections, body_start),
        "relations": {
            "composes_with": _extract_relations(lines, sections, "composes with", body_start),
            "delegates_to": _extract_relations(lines, sections, "delegates to", body_start),
        },
        "references": sorted(set(_URL.findall(raw))),
    }


def _parse_frontmatter(lines: list[str], relative_path: str) -> tuple[dict[str, Any], int]:
    """Parse the YAML frontmatter block with a real YAML parser.

    A hand-rolled line-by-line parser previously lived here. Real SKILL.md
    corpora in the wild (mukul975/Anthropic-Cybersecurity-Skills: 818
    skills) use YAML sequences, plain and quoted multi-line scalars, and
    sequences nested inside mappings -- each one required its own special
    case, and a list-of-mappings shape (`techniques: / - id: ... / name:
    ...`) surfaced as soon as the previous gaps were closed. Recognizing
    that as the general shape of the problem (YAML is recursive; a flat or
    one-level-nested hand-rolled parser will always have one more shape to
    chase), this now delegates to `yaml.safe_load` -- the actual root-cause
    fix rather than another special case.
    """
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{relative_path}: missing frontmatter opening delimiter")
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise ValueError(f"{relative_path}: unterminated frontmatter") from exc

    raw_yaml = "\n".join(lines[1:end])
    parsed = _load_yaml_with_colon_repair(raw_yaml, relative_path)

    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        raise ValueError(f"{relative_path}: frontmatter must be a YAML mapping, got {type(parsed).__name__}")

    return _normalize_yaml_value(parsed), end + 1


# A plain top-level "key: <free text>" line. Used only to decide whether a
# line PyYAML rejected can be safely auto-quoted -- not a general
# frontmatter grammar (real YAML parsing is `yaml.safe_load` itself).
_PLAIN_KEY_LINE = re.compile(r"^([A-Za-z0-9_-]+):[ \t](.*)$")
_YAML_SAFE_LEADING_CHARS = ("'", '"', "[", "{", "|", ">", "-")
_MAX_COLON_REPAIR_ATTEMPTS = 100


def _quote_yaml_scalar(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _load_yaml_with_colon_repair(raw_yaml: str, relative_path: str) -> Any:
    """Parse frontmatter YAML, auto-quoting one specific, common real-world
    deviation from strict YAML: a plain (unquoted) scalar value containing
    an unescaped `: ` later in the same line, e.g.:

        description: Use when live-triaging a host: "acquire the disk",
          "grab a memory dump"...

    YAML's grammar does not allow this (an unquoted `: ` inside a plain
    scalar is ambiguous with a new mapping key), but it is an extremely
    common way to write a free-text description by hand, and strict
    rejection would break the large majority of already-working,
    hand-written SKILL.md files in this project's own corpus -- a worse
    regression than the real-world structural gaps (YAML sequences,
    multi-line scalars, nested sequences) that motivated using a real YAML
    parser in the first place.

    On a YAML scanner/parser error, this looks at PyYAML's own reported
    line, and only if that exact line is a complete top-level "key: text"
    pair whose value does not already start with YAML-meaningful syntax
    (a quote, a sequence/mapping/block indicator), it re-quotes that one
    line's value and retries. A problem on any other kind of line (a
    multi-line scalar continuation, a nested sequence item, etc.) is left
    as the real, honest YAML error -- this is a narrow, targeted repair
    for one observed real-world pattern, not a general fallback parser.
    """
    working_lines = raw_yaml.split("\n")
    last_error: yaml.YAMLError | None = None
    for _ in range(_MAX_COLON_REPAIR_ATTEMPTS):
        text = "\n".join(working_lines)
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            last_error = exc
            mark = getattr(exc, "problem_mark", None)
            if mark is None or not (0 <= mark.line < len(working_lines)):
                break
            problem_line = working_lines[mark.line]
            match = _PLAIN_KEY_LINE.match(problem_line)
            if not match:
                break
            value = match.group(2)
            if not value or value.lstrip()[:1] in _YAML_SAFE_LEADING_CHARS:
                break
            working_lines[mark.line] = f"{match.group(1)}: {_quote_yaml_scalar(value)}"
    raise ValueError(f"{relative_path}: invalid frontmatter YAML: {last_error}") from last_error


def _normalize_yaml_value(value: Any) -> Any:
    """Stringify every scalar leaf so frontmatter metadata keeps the shape
    every caller already expects (name/description/etc. as plain strings),
    regardless of whether the source YAML wrote a value quoted or not --
    the previous hand-rolled parser never produced anything but strings
    for a scalar, since it had no type inference at all. An unquoted
    `version: 1.1` must stay the string "1.1", not become a float: this
    project never allows a float into any downstream decision path, and a
    frontmatter scalar is exactly the kind of value that should not be the
    first float smuggled in by a parser upgrade.
    """
    if isinstance(value, dict):
        return {str(key): _normalize_yaml_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_yaml_value(item) for item in value]
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        # Frontmatter metadata is descriptive text carried through to
        # reports, never arithmetic -- stringifying here (rather than
        # rejecting) matches what the previous hand-rolled parser always
        # did for every scalar, quoted or not. No float value is retained
        # as a float past this point, which is what the project's
        # no-float-in-the-decision-path invariant actually requires.
        return str(value)
    return str(value)


def _section_ranges(lines: list[str], body_start: int) -> dict[str, tuple[int, int]]:
    """Map each Markdown heading's lowercased title to the line range it
    governs (up to the next heading).

    A line inside a fenced code block that happens to start with "#" (a
    shell/Python comment, most commonly) is not a Markdown heading, even
    though it matches `_HEADING`'s regex exactly -- fenced code is opaque
    to the surrounding document's heading structure. Observed live on
    mukul975/Anthropic-Cybersecurity-Skills: 544/818 skills contain at
    least one such comment, producing 10,749 phantom headings against
    11,332 real ones corpus-wide (nearly 1:1). A phantom heading like
    "# Check for known UEFI malware patterns" then matches the
    Checks/Verification section filter in `_extract_checks` by substring,
    misclassifying an unrelated reference list as a batch of unverifiable
    checks -- corrupting not just check extraction but every other
    consumer of this function's output (procedural steps, composition/
    delegation relations). Excluding code-block lines here, once, fixes
    all of those consumers at the source rather than requiring each one
    to re-derive and apply the same exclusion independently.
    """
    code_lines = _code_block_lines(lines, body_start)
    headings: list[tuple[int, str]] = []
    for index in range(body_start, len(lines)):
        if index in code_lines:
            continue
        match = _HEADING.match(lines[index])
        if match:
            headings.append((index, match.group("title").strip().lower()))
    ranges: dict[str, tuple[int, int]] = {}
    for position, (start, title) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        ranges[title] = (start + 1, end)
    return ranges


def _code_block_lines(lines: list[str], body_start: int) -> set[int]:
    """Return the set of line indices inside code blocks (between ``` fences)."""
    code_lines: set[int] = set()
    in_code = False
    for index in range(body_start, len(lines)):
        if _CODE_FENCE.match(lines[index]):
            in_code = not in_code
            continue
        if in_code:
            code_lines.add(index)
    return code_lines


# Trigger extraction patterns. These capture the clause that describes
# when the skill should be activated, from the description text.
_TRIGGER_PATTERNS = [
    re.compile(
        r"\buse\s+(?:this skill\s+)?(?:whenever|when|if|for)\b\s*(.+?)(?:[.;]|\Z)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\btrigger(?:s|ed)?\s+(?:on|when|for)\b\s*(.+?)(?:[.;]|\Z)",
        re.IGNORECASE | re.DOTALL,
    ),
]


def _extract_trigger(description: str) -> dict[str, Any]:
    """Extract the trigger clause from a skill's description.

    Returns a dict with:
    - text: the raw trigger clause text (or "" if no trigger found)
    - found: whether a trigger pattern was matched
    """
    for pattern in _TRIGGER_PATTERNS:
        match = pattern.search(description)
        if match:
            raw = match.group(1).strip()
            # Truncate at reasonable length to avoid capturing the entire
            # description as a trigger clause.
            if len(raw) > 300:
                raw = raw[:300]
            return {"text": raw, "found": True}
    return {"text": "", "found": False}


def _extract_rules(lines: list[str], body_start: int) -> list[dict[str, Any]]:
    """Extract normative rules from a skill body.

    Three extraction styles are recognized, in priority order:

    1. RFC-2119 modals (MUST, SHOULD, MAY) — the original style.
    2. Negative starters (Never, Always, Do not, Don't) — common in
       prose-style skills that use absoluteness instead of modals.
    3. Imperative starters (Ensure, Require, Prevent, Avoid, Validate,
       ...) — normative constraint verbs at the start of a line.

    All three produce rules with extraction_status "candidate". Styles 2
    and 3 use modality "NEVER", "ALWAYS", "MUST_NOT", or "IMPERATIVE".
    The subject is "" for non-RFC-2119 rules (no NLP object extraction).

    Code blocks (between ``` fences) and headings are skipped.
    """
    rules: list[dict[str, Any]] = []
    code_lines = _code_block_lines(lines, body_start)
    for index in range(body_start, len(lines)):
        if index in code_lines:
            continue
        line = lines[index]
        if _HEADING.match(line):
            continue
        # 1. RFC-2119 modals (existing behavior).
        match = _MODALITY.search(line)
        if match:
            raw_modality = match.group(1)
            modality = raw_modality.replace(" ", "_").upper()
            text = line.strip()
            subject = _extract_subject(text, raw_modality)
            conditions = _extract_conditions(text)
            claims = _extract_claims(text)
            rules.append({
                "id": f"rule-{len(rules) + 1:04d}",
                "extraction_status": "candidate",
                "modality": modality,
                "subject": subject,
                "conditions": conditions,
                "claims": claims,
                "text": text,
                "source_span": {"line": index + 1, "column": match.start(1) + 1},
            })
            continue
        # 2. Negative starters (Never, Always, Do not, Don't).
        neg_matched = False
        for pattern, neg_modality in _NORMATIVE_STARTERS:
            if pattern.match(line):
                text = line.strip()
                conditions = _extract_conditions(text)
                claims = _extract_claims(text)
                rules.append({
                    "id": f"rule-{len(rules) + 1:04d}",
                    "extraction_status": "candidate",
                    "modality": neg_modality,
                    "subject": "",
                    "conditions": conditions,
                    "claims": claims,
                    "text": text,
                    "source_span": {"line": index + 1, "column": 1},
                })
                neg_matched = True
                break
        if neg_matched:
            continue
        # 3. Imperative starters (normative constraint verbs).
        if _IMPERATIVE_STARTER.match(line):
            text = line.strip()
            conditions = _extract_conditions(text)
            claims = _extract_claims(text)
            rules.append({
                "id": f"rule-{len(rules) + 1:04d}",
                "extraction_status": "candidate",
                "modality": "IMPERATIVE",
                "subject": "",
                "conditions": conditions,
                "claims": claims,
                "text": text,
                "source_span": {"line": index + 1, "column": 1},
            })
    return rules


# Condition extraction patterns. Each pattern captures a condition
# clause from rule text. The type determines how the condition affects
# the rule's polarity:
#   "exception" — inverts the modality for this condition (except for, unless)
#   "scope" — restricts the modality to this condition (when, if, for, during, while)
_CONDITION_PATTERNS = [
    # Exception patterns (invert polarity).
    (re.compile(r"\bexcept\s+(?:for\s+)?(.+?)(?:[.;,]|$)", re.IGNORECASE), "exception"),
    (re.compile(r"\bunless\s+(.+?)(?:[.;,]|$)", re.IGNORECASE), "exception"),
    # Scope patterns (restrict polarity).
    (re.compile(r"\bwhen\s+(.+?)(?:[.;,]|$)", re.IGNORECASE), "scope"),
    (re.compile(r"\bif\s+(.+?)(?:[.;,]|$)", re.IGNORECASE), "scope"),
    (re.compile(r"\bduring\s+(.+?)(?:[.;,]|$)", re.IGNORECASE), "scope"),
    (re.compile(r"\bwhile\s+(.+?)(?:[.;,]|$)", re.IGNORECASE), "scope"),
    # "for X" is ambiguous (could be a recipient), but in normative rules
    # it often introduces a scope condition. We extract it as scope.
    (re.compile(r"\bfor\s+(.+?)(?:[.;,]|$)", re.IGNORECASE), "scope"),
]


def _extract_conditions(rule_text: str) -> list[dict[str, str]]:
    """Extract condition clauses from a normative rule.

    Returns a list of {text, type} where type is "exception" (inverts
    the modality) or "scope" (restricts the modality). The text is
    normalized to lowercase and stripped.
    """
    conditions: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for pattern, cond_type in _CONDITION_PATTERNS:
        for match in pattern.finditer(rule_text):
            raw = match.group(1).strip().lower()
            # Strip articles and trailing punctuation.
            for article in ("the ", "a ", "an "):
                if raw.startswith(article):
                    raw = raw[len(article):]
            raw = raw.strip(" ,;:.")
            if len(raw) < 2:
                continue
            key = (raw, cond_type)
            if key in seen:
                continue
            seen.add(key)
            conditions.append({"text": raw, "type": cond_type})
    # Sort for determinism.
    conditions.sort(key=lambda c: (c["text"], c["type"]))
    return conditions


# Claim extraction patterns. A claim is a factual assertion that carries
# a numeric value or standards reference and therefore needs provenance.
# Each claim is {text, kind, has_provenance}.
_CLAIM_VALUE_PATTERNS = [
    (re.compile(r"\b\d+%(?!\w)"), "percentage"),
    (re.compile(r"\b\d+\s*(?:ms|seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b", re.IGNORECASE), "time"),
    (re.compile(r"\b\d+\s*(?:x|times|iterations?|attempts?|retries?)\b", re.IGNORECASE), "count"),
    (re.compile(r"\b(?:NIST|OWASP|CWE|CVE|MITRE|ISO|RFC|W3C|WCAG|WCA)\b\s*(?:SP\s*)?\d+", re.IGNORECASE), "standard"),
    (re.compile(r"\b\d{4}\b"), "year"),
]

# Provenance indicators. If any of these appear in the rule text, the
# claim is considered to have provenance.
_PROVENANCE_PATTERNS = [
    re.compile(r"\b(?:per|according to|source:|see|ref:|citation:|from)\b", re.IGNORECASE),
    re.compile(r"\[(?:NIST|OWASP|CWE|CVE|MITRE|ISO|RFC|W3C|WCAG|WCA)\b", re.IGNORECASE),
    re.compile(r"\b(?:NIST|OWASP|CWE|CVE|MITRE|ISO|RFC|W3C|WCAG|WCA)\b\s*(?:SP\s*)?\d+", re.IGNORECASE),
    re.compile(r"\([^)]*\d{4}\)"),
    re.compile(r"https?://"),
]


def _extract_claims(rule_text: str) -> list[dict[str, Any]]:
    """Extract claims from a rule's text.

    A claim is a factual assertion with a numeric value or standards
    reference. Each claim records:
    - text: the matched value
    - kind: the claim kind (percentage, time, count, standard, year)
    - has_provenance: whether the rule text contains a provenance indicator
    """
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()
    has_provenance = any(p.search(rule_text) for p in _PROVENANCE_PATTERNS)
    for pattern, kind in _CLAIM_VALUE_PATTERNS:
        for match in pattern.finditer(rule_text):
            value = match.group(0).strip()
            key = f"{kind}:{value}"
            if key in seen:
                continue
            seen.add(key)
            claims.append({
                "text": value,
                "kind": kind,
                "has_provenance": has_provenance,
            })
    # Sort for determinism.
    claims.sort(key=lambda c: (c["kind"], c["text"]))
    return claims


def _extract_subject(rule_text: str, raw_modality: str) -> str:
    """Extract the subject of a normative rule.

    The subject is the noun phrase before the modal verb, normalized
    to lowercase with leading articles and markdown formatting stripped.
    If the modal verb is at the start of the line (after stripping
    markdown), there is no explicit subject and we return "".
    """
    idx = rule_text.find(raw_modality)
    if idx <= 0:
        return ""
    subject = rule_text[:idx].strip()
    # Strip markdown formatting: bold (**), italic (*), code (`), underline (_)
    subject = re.sub(r"\*+|`+|_+", " ", subject)
    # Strip leading list markers, table pipes, heading markers
    subject = re.sub(r"^[\s|\-*+#>]+", "", subject)
    # Normalize: lowercase, strip leading articles, strip trailing punctuation
    subject = subject.lower()
    for article in ("the ", "a ", "an ", "you ", "your "):
        if subject.startswith(article):
            subject = subject[len(article):]
    subject = subject.strip(" ,;:.")
    return subject


def _extract_procedural_steps(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    body_start: int,
) -> list[dict[str, Any]]:
    """Extract procedural steps from a skill body.

    Procedural steps are found in:
    - Sections titled "## Steps", "## Procedure", "## How to", "## Process", etc.
    - Numbered lists anywhere in the body (1. ... 2. ...)
    - Bullet lists with action verbs in procedural sections
    - Bullet lists elsewhere whose text begins with an action verb
      (prose-embedded steps in non-procedural sections)

    The action-verb heuristic for non-procedural bullets avoids extracting
    explanatory bullets ("This is important because ...") as steps. Code
    blocks and headings are skipped.
    """
    steps: list[dict[str, Any]] = []
    seen_lines: set[int] = set()
    code_lines = _code_block_lines(lines, body_start)

    # 1. Extract from procedural sections.
    for title, (start, end) in sections.items():
        if not any(ps in title for ps in _PROCEDURAL_SECTIONS):
            continue
        for index in range(start, end):
            if index in seen_lines or index in code_lines:
                continue
            # Numbered list
            num_match = _NUMBERED.match(lines[index])
            if num_match:
                steps.append({
                    "id": f"step-{len(steps) + 1:04d}",
                    "text": num_match.group("value"),
                    "source_span": {"line": index + 1, "column": 1},
                })
                seen_lines.add(index)
                continue
            # Bullet list
            bullet_match = _BULLET.match(lines[index])
            if bullet_match:
                steps.append({
                    "id": f"step-{len(steps) + 1:04d}",
                    "text": bullet_match.group("value"),
                    "source_span": {"line": index + 1, "column": 1},
                })
                seen_lines.add(index)

    # 2. Extract numbered lists from anywhere in the body.
    for index in range(body_start, len(lines)):
        if index in seen_lines or index in code_lines:
            continue
        num_match = _NUMBERED.match(lines[index])
        if num_match:
            steps.append({
                "id": f"step-{len(steps) + 1:04d}",
                "text": num_match.group("value"),
                "source_span": {"line": index + 1, "column": 1},
            })
            seen_lines.add(index)

    # 3. Extract action-verb bullets from non-procedural sections
    #    (prose-embedded steps). This catches skills that embed their
    #    procedure in ordinary prose bullets rather than a dedicated
    #    "Steps" section. The first word must be an action verb to
    #    avoid extracting explanatory bullets. Bullets in Checks or
    #    Verification sections are skipped — those are checks, not
    #    steps, and are extracted by _extract_checks.
    check_section_lines: set[int] = set()
    for title, (start, end) in sections.items():
        if "check" in title or "verification" in title:
            check_section_lines.update(range(start, end))
    for index in range(body_start, len(lines)):
        if index in seen_lines or index in code_lines:
            continue
        if index in check_section_lines:
            continue
        line = lines[index]
        if _HEADING.match(line):
            continue
        bullet_match = _BULLET.match(line)
        if not bullet_match:
            continue
        text = bullet_match.group("value")
        first_word = text.split(" ", 1)[0].lower().strip(".,;:()")
        if first_word in _ACTION_VERBS:
            steps.append({
                "id": f"step-{len(steps) + 1:04d}",
                "text": text,
                "source_span": {"line": index + 1, "column": 1},
            })
            seen_lines.add(index)

    return steps


def _extract_checks(
    lines: list[str],
    sections: dict[str, tuple[int, int]],
    body_start: int,
) -> list[dict[str, Any]]:
    """Extract checks from a skill body.

    Checks are found in:
    - Sections titled "## Checks" or "## Verification" (existing behavior).
    - Lines anywhere in the body that start with a verification verb
      (verify, check, test, assert, confirm, demonstrate, prove).

    Code blocks and headings are skipped. Lines already extracted from
    a Checks/Verification section are not re-extracted.
    """
    checks: list[dict[str, Any]] = []
    seen_lines: set[int] = set()
    code_lines = _code_block_lines(lines, body_start)

    # 1. Extract from Checks/Verification sections.
    for title, (start, end) in sections.items():
        if "check" not in title and "verification" not in title:
            continue
        for index in range(start, end):
            if index in code_lines:
                continue
            match = _BULLET.match(lines[index])
            if match:
                text = match.group("value")
                checks.append({
                    "id": f"check-{len(checks) + 1:04d}",
                    "text": text,
                    "oracle_kind": _extract_oracle_kind(text),
                    "source_span": {"line": index + 1, "column": 1},
                })
                seen_lines.add(index)

    # 2. Extract verification-starter lines from anywhere in the body.
    for index in range(body_start, len(lines)):
        if index in seen_lines or index in code_lines:
            continue
        line = lines[index]
        if _HEADING.match(line):
            continue
        if not _VERIFICATION_STARTER.match(line):
            continue
        # Strip leading bullet/number markers for the check text.
        text = line.strip()
        text = re.sub(r"^\s*(?:[-*+]\s+|\d+\.\s+)", "", text)
        checks.append({
            "id": f"check-{len(checks) + 1:04d}",
            "text": text,
            "oracle_kind": _extract_oracle_kind(text),
            "source_span": {"line": index + 1, "column": 1},
        })
        seen_lines.add(index)

    return checks


# Oracle kind extraction. Each check is classified by how it can be
# verified. The oracle_kind indicates what kind of oracle the check
# implies:
#   "question"    — the check is a question (has a question mark)
#   "command"     — the check is a command (verify, assert, run, check,
#                   confirm, test, query, inspect, does)
#   "checkbox"    — the check is a checkbox item ([ ] or [x])
#   "unknown"     — the check has no extractable oracle indicator
_ORACLE_PATTERNS = [
    (re.compile(r"\?\s*$"), "question"),
    (re.compile(r"^\s*\[\s*[xX ]\s*\]"), "checkbox"),
    (re.compile(rf"\b(?:{_VERIFICATION_VERB_ALTERNATION})\b", re.IGNORECASE), "command"),
]


def _extract_oracle_kind(check_text: str) -> str:
    """Classify a check by its implied oracle kind.

    Returns "question", "checkbox", "command", or "unknown".
    """
    for pattern, kind in _ORACLE_PATTERNS:
        if pattern.search(check_text):
            return kind
    return "unknown"


def _extract_relations(
    lines: list[str], sections: dict[str, tuple[int, int]], section_name: str, body_start: int
) -> list[str]:
    relations: list[str] = []
    code_lines = _code_block_lines(lines, body_start)
    for title, (start, end) in sections.items():
        if section_name not in title:
            continue
        for index in range(start, end):
            if index in code_lines:
                continue
            match = _BULLET.match(lines[index])
            if match:
                relations.append(match.group("value"))
    return sorted(set(relations))

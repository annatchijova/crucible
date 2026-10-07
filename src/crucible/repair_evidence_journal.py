"""Offline reconciliation of the three local L7 evidence representations."""

from __future__ import annotations

import os
from pathlib import Path
import stat
from typing import Any

from .capture_contract import strict_json
from .ir import canonical_bytes
from .repair_evidence import MAX_EVIDENCE_BYTES, verify_repair_evidence

JOURNAL_CHECK_VERSION = "crucible-repair-evidence-journal-check/v1"


def _read_regular(path: Path, limit: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("not a bounded regular file")
        chunks = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if len(data) > limit:
            raise ValueError("file grew beyond byte limit")
        return data
    finally:
        os.close(fd)


def verify_repair_evidence_journal(directory: str | os.PathLike[str]) -> dict[str, Any]:
    """Check the sealed bundle against its JSONL journal and raw captures.

    This proves only local representation agreement. It does not authenticate
    the provider or externally anchor the evidence directory.
    """
    result = {"schema_version": JOURNAL_CHECK_VERSION, "status": "INVALID_EVIDENCE",
              "reason": "journal-read-or-consistency-failed"}
    root = Path(directory).absolute()
    try:
        root_info = root.lstat()
        if not stat.S_ISDIR(root_info.st_mode):
            return result
        bundle_data = _read_regular(root / "bundle.json", MAX_EVIDENCE_BYTES)
        bundle = strict_json(bundle_data.decode("utf-8"))
        if not verify_repair_evidence(bundle):
            return result
        events = bundle["events"]

        raw_dir = root / "raw-captures"
        raw_info = raw_dir.lstat()
        if not stat.S_ISDIR(raw_info.st_mode):
            return result
        expected_raw = {f"{index:04d}.json" for index in range(len(events))}
        actual_raw = {entry.name for entry in raw_dir.iterdir()}
        if actual_raw != expected_raw:
            return {**result, "status": "DIVERGED",
                    "reason": "raw-capture-file-set-differs"}
        raw_budget = len(bundle_data)
        for index, event in enumerate(events):
            raw_data = _read_regular(raw_dir / f"{index:04d}.json", raw_budget)
            raw_budget -= len(raw_data)
            if raw_data != canonical_bytes(event["capture"]):
                return {**result, "status": "DIVERGED",
                        "reason": "raw-capture-content-differs"}

        expected_journal = b"".join(canonical_bytes(event) + b"\n" for event in events)
        journal_data = _read_regular(root / "events.jsonl", MAX_EVIDENCE_BYTES)
        if journal_data != expected_journal:
            return {**result, "status": "DIVERGED",
                    "reason": "event-journal-content-differs"}
        return {"schema_version": JOURNAL_CHECK_VERSION, "status": "MATCH",
                "reason": None, "event_count": len(events),
                "bundle_digest": bundle["bundle_digest"]}
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        return result

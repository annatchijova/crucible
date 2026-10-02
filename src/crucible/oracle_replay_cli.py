"""Offline CLI boundary for deterministic observation replay."""

from __future__ import annotations

import json
import os
import stat
import sys

from .oracle_replay import reevaluate_observations, replay_observations
from .replay import MAX_BUNDLE_BYTES, load_bundle


def run_oracle_replay_command(mode: str, filename: str) -> int:
    """Read one bounded bundle and emit a sealed replay result.

    Exit 0 means exact replay matched, or explicit re-evaluation matched.
    Exit 1 means the oracle could not replay the evidence or observations
    diverged. Exit 2 is an input or operational error. Diagnostics do not
    include private bundle content.
    """
    if mode not in ("replay_bundle", "reevaluate_bundle"):
        raise ValueError("unknown oracle replay mode")

    try:
        descriptor = os.open(
            filename,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("bundle input must be a regular file")
            with os.fdopen(descriptor, "rb", closefd=False) as source:
                raw = source.read(MAX_BUNDLE_BYTES + 1)
        finally:
            os.close(descriptor)
        if len(raw) > MAX_BUNDLE_BYTES:
            raise ValueError("bundle exceeds byte limit")
        bundle = load_bundle(raw.decode("utf-8"))
        if mode == "replay_bundle":
            result = replay_observations(bundle)
        else:
            result = reevaluate_observations(bundle)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if result["outcome"] in ("MATCH", "REEVALUATED_MATCH") else 1
    except (OSError, UnicodeError, ValueError):
        print("Oracle replay failed: invalid, unreadable, or unsupported bundle.", file=sys.stderr)
        return 2

"""Private, append-only evidence for one authorized L7 provider run.

This is a capture wrapper around the existing repair loop, not a new repair
policy. Raw exchanges are persisted and fsynced before their responses are
projected into L7 observations. A chain digest detects accidental edits; it is
not provider authentication or a signature.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import time
from typing import Any

from . import behavioral
from .behavioral import NebiusExecutor, TASK_FIXTURE
from .bob import LLMProposer
from .capture_bundle import oracle_identity
from .capture_contract import capture_projection, validate_capture
from .ir import canonical_bytes, digest_bytes, digest_payload
from .repair_loop import LOOP_FIXTURE, run_repair_loop

EVIDENCE_VERSION = "crucible-repair-evidence/v1"
MAX_EVIDENCE_BYTES = 32_000_000


class RepairEvidenceJournal:
    """Create a fresh private directory and fsync each captured exchange."""

    def __init__(self, path: str | os.PathLike[str]):
        if os.name != "posix":
            raise OSError("private repair evidence currently requires POSIX")
        self.path = Path(path).absolute()
        self.path.mkdir(mode=0o700, parents=True, exist_ok=False)
        os.chmod(self.path, 0o700)
        self.raw_path = self.path / "raw-captures"
        self.raw_path.mkdir(mode=0o700)
        self.events_path = self.path / "events.jsonl"
        fd = os.open(self.events_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        self.events: list[dict[str, Any]] = []
        self._sync_dir(self.path.parent)

    @staticmethod
    def _sync_dir(path: Path) -> None:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def record(self, stage: str, capture: dict[str, Any]) -> dict[str, Any]:
        sequence = len(self.events)
        raw_name = f"{sequence:04d}.json"
        raw_file = self.raw_path / raw_name
        raw_bytes = canonical_bytes(capture)
        raw_fd = os.open(raw_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            view = memoryview(raw_bytes)
            while view:
                written = os.write(raw_fd, view)
                view = view[written:]
            os.fsync(raw_fd)
        finally:
            os.close(raw_fd)
        self._sync_dir(self.raw_path)

        # Raw response bytes are now durable; only now parse/project them.
        projection_request, projection_response = capture_projection(capture)
        event = {
            "sequence": sequence,
            "stage": stage,
            "raw_capture_file": f"raw-captures/{raw_name}",
            "capture": capture,
            "request_projection": projection_request,
            "response_projection": projection_response,
            "previous_event_digest": self.events[-1]["event_digest"] if self.events else None,
        }
        event["event_digest"] = digest_payload(event)
        line = canonical_bytes(event) + b"\n"
        current = self.events_path.stat().st_size
        if current + len(line) > MAX_EVIDENCE_BYTES:
            raise ValueError("repair evidence size limit exceeded")
        fd = os.open(self.events_path, os.O_WRONLY | os.O_APPEND)
        try:
            view = memoryview(line)
            while view:
                written = os.write(fd, view)
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        self.events.append(event)
        return event

    def finish(self, *, corpus: dict[str, str], task: dict[str, Any],
               finding_index: int, report: dict[str, Any]) -> dict[str, Any]:
        source_digests = {
            name: digest_bytes(text.encode("utf-8"))
            for name, text in sorted(corpus.items())
        }
        bundle = {
            "schema_version": EVIDENCE_VERSION,
            "created_unix_ns": time.time_ns(),
            "runtime": {"python": sys.version},
            "provider": "nebius-token-factory",
            "request_adapter": "nebius-chat-guidance/v1",
            "oracle": oracle_identity(),
            "loop_version": report.get("loop_version"),
            "source": {
                "corpus": corpus,
                "corpus_digests": source_digests,
                "task": task,
                "task_digest": digest_payload(task),
                "finding_index": finding_index,
                "base_audit_digest": report.get("base_audit_digest"),
            },
            "events": self.events,
            "report": report,
            "limitations": [
                "Capture records locally observed HTTP bodies, not proof of provider receipt, identity, or unchanged server execution.",
                "No retry was performed. A process failure before a response was returned can leave an attempted request without a captured response body.",
                "The event chain detects internal edits only when verified against a trusted digest; it is not externally anchored.",
                "One run is not a stability benchmark or independent evaluation.",
            ],
        }
        bundle["bundle_digest"] = digest_payload(bundle)
        encoded = canonical_bytes(bundle)
        if len(encoded) > MAX_EVIDENCE_BYTES:
            raise ValueError("repair evidence bundle size limit exceeded")
        destination = self.path / "bundle.json"
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            view = memoryview(encoded)
            while view:
                written = os.write(fd, view)
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        self._sync_dir(self.path)
        return bundle


class _CapturedProposer(LLMProposer):
    def __init__(self, journal: RepairEvidenceJournal, api_key: str | None = None):
        super().__init__(api_key=api_key)
        self.journal = journal

    def propose(self, finding, skill_text, context):
        system = (
            "You are a methodology repair engine. You receive a finding from a skill audit and the current skill text. "
            "Propose a repaired version of the skill text that resolves the finding without introducing new issues. "
            "Output ONLY the repaired skill text, no explanation."
        )
        user = self._build_prompt(finding, skill_text, context)
        executor = NebiusExecutor(model=self.NEBIUS_MODEL, temperature=0,
                                  max_tokens=1000, api_key=self.api_key)
        capture = executor.capture_exchange(system, user)
        event = self.journal.record("repair_proposal", capture)
        response = event["response_projection"]
        metadata = {"model": self.NEBIUS_MODEL, "proposer": "llm-nebius",
                    "response_id": response.get("response_id"),
                    "finish_reason": response.get("finish_reason"),
                    "usage": response.get("usage"),
                    "truncated": response.get("truncated")}
        if not _usable(response):
            return {**metadata, "proposed_text": None,
                    "blocked": capture["status"] == "BLOCKED",
                    "error": response.get("error") or "incomplete-provider-response",
                    "rationale": "provider response retained but not eligible for repair"}
        output = response["output"]
        return {**metadata, "proposed_text": output if output.strip() else None,
                "blocked": False, "rationale": "generated by Nemotron via Nebius Token Factory"}


class _CapturedExecutor:
    model = behavioral.NEBIUS_DEFAULT_MODEL
    provider = "nebius-token-factory"

    def __init__(self, journal: RepairEvidenceJournal, api_key: str | None = None):
        self.journal = journal
        self.executor = NebiusExecutor(api_key=api_key)
        self.temperature = self.executor.temperature
        self.max_tokens = self.executor.max_tokens

    def execute(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        capture = self.executor.capture_exchange(system_prompt, user_prompt)
        event = self.journal.record("behavioral_observation", capture)
        response = event["response_projection"]
        if not _usable(response):
            return {"output": "", "error": response.get("error") or "incomplete-provider-response",
                    "model": self.model, "provider": self.provider,
                    "temperature": self.temperature, "max_tokens": self.max_tokens,
                    "usage": response.get("usage"), "response_id": response.get("response_id"),
                    "finish_reason": response.get("finish_reason"),
                    "truncated": response.get("truncated")}
        return {"output": response["output"], "error": None, "model": self.model,
                "provider": self.provider, "temperature": self.temperature,
                "max_tokens": self.max_tokens, "usage": response.get("usage"),
                "response_id": response.get("response_id"),
                "finish_reason": response.get("finish_reason"), "truncated": False}


def _usable(response: dict[str, Any]) -> bool:
    return (response.get("status") == "COMPLETED"
            and response.get("truncated") is False
            and response.get("finish_reason") is not None
            and response.get("usage") is not None
            and response.get("error") is None)


def run_captured_repair(path: str | os.PathLike[str], *, api_key: str | None = None,
                        corpus: dict[str, str] | None = None,
                        task: dict[str, Any] | None = None,
                        finding_index: int = 0) -> dict[str, Any]:
    """Run one actual L7 flow, persisting raw evidence at every response edge."""
    corpus = dict(LOOP_FIXTURE if corpus is None else corpus)
    task = dict(TASK_FIXTURE if task is None else task)
    journal = RepairEvidenceJournal(path)
    executor = _CapturedExecutor(journal, api_key=api_key)
    proposer = _CapturedProposer(journal, api_key=api_key)
    report = run_repair_loop(corpus=corpus, task=task, finding_index=finding_index,
                             proposer=proposer, executor=executor)
    # L7 predates completeness-aware decisions. Never let absent/incomplete
    # remote observations inherit ACCEPTED from an empty-string lexical check.
    if (report.get("outcome") == "ACCEPTED"
            and any(not _usable(event["response_projection"]) for event in journal.events)):
        report["outcome"] = "ERROR"
        report["rejection_reason"] = "INCOMPLETE_PROVIDER_RESPONSE"
        report["loop_digest"] = digest_payload({k: v for k, v in report.items() if k != "loop_digest"})
    return journal.finish(corpus=corpus, task=task,
                          finding_index=finding_index, report=report)


def verify_repair_evidence(bundle: dict[str, Any]) -> bool:
    """Verify bundle seal and ordered event chain; does not contact Nebius."""
    if type(bundle) is not dict or bundle.get("schema_version") != EVIDENCE_VERSION:
        return False
    if bundle.get("bundle_digest") != digest_payload(
            {k: v for k, v in bundle.items() if k != "bundle_digest"}):
        return False
    previous = None
    for sequence, event in enumerate(bundle.get("events", [])):
        if event.get("sequence") != sequence or event.get("previous_event_digest") != previous:
            return False
        if event.get("raw_capture_file") != f"raw-captures/{sequence:04d}.json":
            return False
        try:
            capture = validate_capture(event.get("capture"))
            request_projection, response_projection = capture_projection(capture)
        except (TypeError, ValueError):
            return False
        if (event.get("request_projection") != request_projection
                or event.get("response_projection") != response_projection):
            return False
        if event.get("event_digest") != digest_payload(
                {k: v for k, v in event.items() if k != "event_digest"}):
            return False
        previous = event["event_digest"]
    report = bundle.get("report", {})
    if report.get("loop_digest") is not None and report["loop_digest"] != digest_payload(
            {k: v for k, v in report.items() if k != "loop_digest"}):
        return False
    source = bundle.get("source", {})
    if source.get("task_digest") != digest_payload(source.get("task")):
        return False
    if source.get("corpus_digests") != {
            name: digest_bytes(text.encode("utf-8"))
            for name, text in sorted(source.get("corpus", {}).items())}:
        return False
    return True

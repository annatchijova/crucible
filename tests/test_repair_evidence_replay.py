"""Offline reconstruction contract for captured L7 decisions."""

from __future__ import annotations

import copy
import json
import sys

import pytest

from crucible.behavioral import NebiusExecutor
from crucible.bob import RuleBasedProposer, _compile_and_audit
from crucible import cli
from crucible.ir import digest_payload
from crucible.repair_evidence import run_captured_repair, verify_repair_evidence
from crucible.repair_loop import LOOP_FIXTURE
from crucible.runtime_capture import capture_exchange


class _Response:
    def __init__(self, body: bytes):
        self.body = body

    def read(self, size: int = -1) -> bytes:
        if not self.body:
            return b""
        result, self.body = self.body[:size], self.body[size:]
        return result

    def getcode(self) -> int:
        return 200

    def close(self) -> None:
        pass


def _accepted_bundle(tmp_path, monkeypatch):
    audit = _compile_and_audit(LOOP_FIXTURE)
    finding = audit["findings"][0]
    skill_name = finding["skill"]
    skill_text = LOOP_FIXTURE[skill_name]
    context = {"finding_index": 0, "total_findings": len(audit["findings"]),
               "all_findings": audit["findings"]}
    proposed = RuleBasedProposer().propose(finding, skill_text, context)["proposed_text"]
    output = (
        "Use a finite retry budget of at most 5 attempts. Read-only operations "
        "may be an exception. Make the operation idempotent before retrying."
    )
    responses = iter([proposed, output, output])

    def fake_capture(self, system_prompt, user_prompt):
        body = json.dumps({
            "id": f"response-{next(fake_capture.ids)}",
            "choices": [{"message": {"content": next(responses)},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        }).encode()
        return capture_exchange(
            self._prepare_request(system_prompt, user_prompt),
            system_prompt=system_prompt, user_prompt=user_prompt, available=True,
            open_request=lambda *_args, **_kwargs: _Response(body),
        )

    fake_capture.ids = iter(range(3))
    monkeypatch.setattr(NebiusExecutor, "capture_exchange", fake_capture)
    return run_captured_repair(tmp_path / "captured", api_key="fixture-only")


def _reseal(bundle):
    bundle["bundle_digest"] = digest_payload(
        {key: value for key, value in bundle.items() if key != "bundle_digest"}
    )


def _reseal_events(bundle):
    previous = None
    for sequence, event in enumerate(bundle["events"]):
        event["sequence"] = sequence
        event["previous_event_digest"] = previous
        event["event_digest"] = digest_payload(
            {key: value for key, value in event.items() if key != "event_digest"}
        )
        previous = event["event_digest"]
    _reseal(bundle)


def test_offline_replay_matches_accepted_capture_without_network(tmp_path, monkeypatch):
    bundle = _accepted_bundle(tmp_path, monkeypatch)
    assert bundle["report"]["outcome"] == "ACCEPTED"
    assert verify_repair_evidence(bundle)
    monkeypatch.setattr(
        NebiusExecutor, "capture_exchange",
        lambda *_args, **_kwargs: pytest.fail("offline replay contacted Nebius"),
    )

    from crucible.repair_evidence_replay import replay_repair_evidence
    result = replay_repair_evidence(bundle)

    assert result["status"] == "MATCH"
    assert result["recorded_outcome"] == result["replayed_outcome"] == "ACCEPTED"
    assert result["decision_digest"].startswith("sha256:")


def test_replay_detects_resealed_decision_tampering(tmp_path, monkeypatch):
    bundle = _accepted_bundle(tmp_path, monkeypatch)
    tampered = copy.deepcopy(bundle)
    tampered["report"]["outcome"] = "REJECTED"
    tampered["report"]["rejection_reason"] = "NEW_FINDINGS"
    tampered["report"]["loop_digest"] = digest_payload(
        {key: value for key, value in tampered["report"].items()
         if key != "loop_digest"}
    )
    _reseal(tampered)
    assert verify_repair_evidence(tampered)

    from crucible.repair_evidence_replay import replay_repair_evidence
    result = replay_repair_evidence(tampered)

    assert result["status"] == "DIVERGED"
    assert result["recorded_outcome"] == "REJECTED"
    assert result["replayed_outcome"] == "ACCEPTED"


def test_replay_refuses_unavailable_loop_version(tmp_path, monkeypatch):
    bundle = _accepted_bundle(tmp_path, monkeypatch)
    bundle["loop_version"] = "crucible-repair-loop/v99"
    _reseal(bundle)

    from crucible.repair_evidence_replay import replay_repair_evidence
    result = replay_repair_evidence(bundle)

    assert result["status"] == "NOT_REPLAYABLE"
    assert result["reason"] == "repair-loop-version-mismatch"


def test_replay_refuses_changed_oracle_before_execution(tmp_path, monkeypatch):
    bundle = _accepted_bundle(tmp_path, monkeypatch)
    bundle["oracle"] = {"oracle_id": "other/v1", "implementation_digest": "sha256:" + "0" * 64}
    _reseal(bundle)
    monkeypatch.setattr(
        "crucible.repair_evidence_replay.oracle_identity",
        lambda: {"oracle_id": "other/v1", "implementation_digest": "sha256:" + "1" * 64},
    )

    from crucible.repair_evidence_replay import replay_repair_evidence
    result = replay_repair_evidence(bundle)

    assert result["status"] == "NOT_REPLAYABLE"
    assert result["reason"] == "oracle-identity-mismatch"


def test_replay_refuses_captured_prompt_from_different_proposer_version(
    tmp_path, monkeypatch
):
    bundle = _accepted_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "crucible.repair_evidence_replay.LLMProposer._build_prompt",
        lambda *_args, **_kwargs: "changed prompt",
    )

    from crucible.repair_evidence_replay import replay_repair_evidence
    result = replay_repair_evidence(bundle)

    assert result["status"] == "NOT_REPLAYABLE"
    assert result["reason"] == "captured-request-does-not-match-replay-input"


def test_replay_rejects_reordered_events_even_when_resealed(tmp_path, monkeypatch):
    bundle = _accepted_bundle(tmp_path, monkeypatch)
    bundle["events"][0]["stage"] = "behavioral_observation"
    bundle["events"][1]["stage"] = "repair_proposal"
    _reseal_events(bundle)
    assert verify_repair_evidence(bundle)

    from crucible.repair_evidence_replay import replay_repair_evidence
    result = replay_repair_evidence(bundle)

    assert result["status"] == "NOT_REPLAYABLE"
    assert result["reason"] == "unexpected-event-sequence"


def test_cli_replays_bundle_offline_and_prints_only_summary(
    tmp_path, monkeypatch, capsys
):
    bundle = _accepted_bundle(tmp_path, monkeypatch)
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["crucible", "--replay-repair-evidence", str(path)])
    monkeypatch.setattr(
        NebiusExecutor, "capture_exchange",
        lambda *_args, **_kwargs: pytest.fail("CLI replay contacted Nebius"),
    )

    assert cli.main() == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["status"] == "MATCH"
    assert "finite retry budget" not in output
    assert "response-0" not in output


def test_cli_maps_deeply_nested_json_to_invalid_evidence(tmp_path, monkeypatch, capsys):
    path = tmp_path / "nested.json"
    path.write_text("[" * 2000 + "0" + "]" * 2000, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["crucible", "--replay-repair-evidence", str(path)])

    assert cli.main() == 1
    assert json.loads(capsys.readouterr().out)["status"] == "INVALID_EVIDENCE"

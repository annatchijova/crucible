import json
from crucible.ir import digest_payload
from crucible.repair_evidence import (
    RepairEvidenceJournal,
    _usable,
    run_captured_repair,
    verify_repair_evidence,
)
from crucible.runtime_capture import capture_exchange


class _Response:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status

    def read(self, size=-1):
        if not self.body:
            return b""
        result, self.body = self.body[:size], self.body[size:]
        return result

    def getcode(self):
        return self.status

    def close(self):
        pass


def _capture(*, finish_reason="stop"):
    from crucible.behavioral import NebiusExecutor

    payload = {
        "id": "resp-test",
        "choices": [{"message": {"content": "bounded retry budget"},
                      "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
    }
    executor = NebiusExecutor(api_key="not-a-real-key")
    return capture_exchange(
        executor._prepare_request("system", "user"),
        system_prompt="system", user_prompt="user", available=True,
        open_request=lambda *_args, **_kwargs: _Response(json.dumps(payload).encode()),
    )


def test_journal_fsyncs_events_and_verifies_chain(tmp_path):
    path = tmp_path / "new-evidence"
    journal = RepairEvidenceJournal(path)
    journal.record("repair_proposal", _capture())
    task = {"task_id": "t", "task_prompt": "p", "properties": []}
    bundle = journal.finish(corpus={"skill": "text"}, task=task,
                           finding_index=0, report={"outcome": "REJECTED"})

    assert (path.stat().st_mode & 0o777) == 0o700
    assert ((path / "events.jsonl").stat().st_mode & 0o777) == 0o600
    assert verify_repair_evidence(bundle)
    assert bundle["events"][0]["capture"]["response"]["body_digest"]
    assert bundle["events"][0]["response_projection"]["response_id"] == "resp-test"

    tampered = json.loads(json.dumps(bundle))
    tampered["events"][0]["stage"] = "behavioral_observation"
    assert not verify_repair_evidence(tampered)


def test_incomplete_response_is_not_usable():
    assert not _usable({"status": "COMPLETED", "truncated": True,
                        "finish_reason": "length", "usage": {}, "error": None})
    assert not _usable({"status": "ERROR", "truncated": None,
                        "finish_reason": None, "usage": None, "error": "invalid"})


def test_captured_run_downgrades_acceptance_if_any_response_is_truncated(tmp_path, monkeypatch):
    from crucible.behavioral import NebiusExecutor
    import crucible.repair_evidence as evidence

    monkeypatch.setattr(NebiusExecutor, "capture_exchange",
                        lambda self, system, user: _capture(finish_reason="length"))
    def _accept_after_provider_calls(**kwargs):
        proposal = kwargs["proposer"].propose(
            {"class": "example", "skill": "retrier", "evidence": "evidence"},
            "original skill", {"finding_index": 0, "total_findings": 1,
                               "all_findings": []})
        kwargs["executor"].execute("original", "task")
        return {"loop_version": "crucible-repair-loop/v1", "outcome": "ACCEPTED",
                "rejection_reason": None, "proposal_seen": proposal.get("proposed_text"),
                "loop_digest": "placeholder"}

    monkeypatch.setattr(evidence, "run_repair_loop", _accept_after_provider_calls)

    bundle = run_captured_repair(tmp_path / "truncated", api_key="configured")

    assert bundle["report"]["outcome"] == "ERROR"
    assert bundle["report"]["rejection_reason"] == "INCOMPLETE_PROVIDER_RESPONSE"
    assert bundle["report"]["loop_digest"] == digest_payload({
        key: value for key, value in bundle["report"].items() if key != "loop_digest"
    })
    assert verify_repair_evidence(bundle)


def test_missing_credential_is_retained_as_blocked_without_provider_call(tmp_path):
    bundle = run_captured_repair(tmp_path / "blocked", api_key="")

    assert bundle["report"]["outcome"] == "BLOCKED"
    assert len(bundle["events"]) == 1
    assert bundle["events"][0]["capture"]["status"] == "BLOCKED"
    assert verify_repair_evidence(bundle)

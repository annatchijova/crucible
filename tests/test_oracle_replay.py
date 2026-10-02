"""Negative controls for exact oracle replay and explicit re-evaluation."""

import io
import json

import pytest

from crucible import cli
from crucible.behavioral import NebiusExecutor
from crucible.capture_bundle import capture_behavioral_bundle
from crucible.capture_contract import capture_projection
from crucible.ir import digest_payload
from crucible.oracle_replay import reevaluate_observations, replay_observations
from crucible.replay import REPLAY_VERSION, dump_bundle


def _seal(bundle):
    bundle["bundle_digest"] = digest_payload(
        {key: value for key, value in bundle.items() if key != "bundle_digest"}
    )
    return bundle


def _bundle(monkeypatch, *, finish_reason="stop", variants=None):
    payload = {
        "id": "fixture-response",
        "choices": [{
            "message": {
                "content": (
                    "Use a bounded budget of at most 3 attempts. "
                    "Read-only requests may be exceptions. "
                    "Make the operation idempotent."
                ),
            },
            "finish_reason": finish_reason,
        }],
        "usage": {"prompt_tokens": 3, "completion_tokens": 6, "total_tokens": 9},
    }

    class Response(io.BytesIO):
        def getcode(self):
            return 200

    def open_request(request, timeout):
        return Response(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr("crucible.behavioral.urllib.request.urlopen", open_request)
    return capture_behavioral_bundle(
        NebiusExecutor(api_key="fixture-key"), variants=variants
    )


def test_pinned_replay_recomputes_exact_property_decisions(monkeypatch):
    bundle = _bundle(monkeypatch)
    original = json.loads(dump_bundle(bundle))
    result = replay_observations(bundle)

    assert result["outcome"] == "MATCH"
    assert all(run["matches_recorded_observations"] for run in result["runs"])
    assert [item["recomputed_status"] for item in result["runs"][0]["properties"]] == [
        "PASS", "PASS", "PASS", "PASS",
    ]
    assert bundle == original
    assert result["result_digest"] == digest_payload(
        {key: value for key, value in result.items() if key != "result_digest"}
    )


def test_resealed_observation_tampering_is_reported_as_divergence(monkeypatch):
    bundle = _bundle(monkeypatch)
    bundle["runs"][0]["observations"][0]["status"] = "FAIL"
    _seal(bundle)

    result = replay_observations(bundle)

    assert result["outcome"] == "DIVERGED"
    assert result["runs"][0]["properties"][0] == {
        "property_id": "P1-mentions-budget",
        "recorded_status": "FAIL",
        "recomputed_status": "PASS",
        "matches": False,
    }


def test_pinned_replay_refuses_different_oracle_before_running_it(monkeypatch):
    bundle = _bundle(monkeypatch)
    monkeypatch.setattr(
        "crucible.oracle_replay.oracle_identity",
        lambda: {"oracle_id": "different/v1", "implementation_digest": "sha256:" + "0" * 64},
    )
    monkeypatch.setattr(
        "crucible.behavioral.run_property_oracle",
        lambda *args, **kwargs: pytest.fail("oracle ran with a mismatched identity"),
    )

    result = replay_observations(bundle)

    assert result["outcome"] == "NOT_REPLAYABLE"
    assert result["recorded_oracle_matches_installed"] is False
    assert result["runs"] == []


def test_explicit_reevaluation_runs_with_changed_identity_without_rewriting_bundle(monkeypatch):
    bundle = _bundle(monkeypatch)
    original = json.loads(dump_bundle(bundle))
    monkeypatch.setattr(
        "crucible.oracle_replay.oracle_identity",
        lambda: {"oracle_id": "different/v1", "implementation_digest": "sha256:" + "0" * 64},
    )

    result = reevaluate_observations(bundle)

    assert result["outcome"] == "REEVALUATED_MATCH"
    assert result["recorded_oracle_matches_installed"] is False
    assert result["recorded_oracle"] == original["oracle"]
    assert bundle == original


def test_incomplete_capture_is_not_sent_to_oracle(monkeypatch):
    bundle = _bundle(monkeypatch, finish_reason="length")
    monkeypatch.setattr(
        "crucible.behavioral.run_property_oracle",
        lambda *args, **kwargs: pytest.fail("incomplete response reached oracle"),
    )

    result = replay_observations(bundle)

    assert result["outcome"] == "NOT_REPLAYABLE"
    assert result["evidence_complete"] is False
    assert result["runs"] == []


def test_v1_bundle_remains_readable_and_replayable(monkeypatch):
    bundle = _bundle(
        monkeypatch,
        variants=[{"variant_id": "one", "skill_text": "Use the guidance."}],
    )
    request, response = capture_projection(bundle["runs"][0]["capture"])
    historical = _seal({
        "schema_version": REPLAY_VERSION,
        "task": bundle["task"],
        "task_digest": bundle["task_digest"],
        "variants": bundle["variants"],
        "oracle": bundle["oracle"],
        "runs": [{
            "variant_id": "one",
            "request": request,
            "response": response,
            "observations": bundle["runs"][0]["observations"],
        }],
    })

    result = replay_observations(historical)

    assert result["source_bundle_version"] == REPLAY_VERSION
    assert result["outcome"] == "MATCH"


@pytest.mark.parametrize("mode", ["--replay-bundle", "--reevaluate-bundle"])
def test_cli_replay_is_offline_and_never_prints_response_body(
    tmp_path, monkeypatch, capsys, mode,
):
    bundle = _bundle(monkeypatch)
    artifact = tmp_path / "bundle.json"
    artifact.write_text(dump_bundle(bundle), encoding="utf-8")
    monkeypatch.setattr(
        "crucible.behavioral.urllib.request.urlopen",
        lambda *args, **kwargs: pytest.fail("replay contacted provider"),
    )
    monkeypatch.setattr("sys.argv", ["crucible", mode, str(artifact)])

    assert cli.main() == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["outcome"] == (
        "MATCH" if mode == "--replay-bundle" else "REEVALUATED_MATCH"
    )
    assert "Make the operation idempotent" not in output

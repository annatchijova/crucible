"""Offline execution of the trusted property oracle over sealed replay bundles.

Replay checks whether retained observations can be reproduced from retained
responses by the exact oracle implementation that the bundle names. Explicit
re-evaluation uses the locally installed oracle even when its identity differs;
it creates a new result and leaves the historical bundle untouched.
"""

from __future__ import annotations

from typing import Any

from . import behavioral
from .capture_bundle import oracle_identity
from .capture_contract import capture_projection
from .ir import digest_payload
from .replay import CAPTURE_REPLAY_VERSION, replay_readiness, validate_bundle

ORACLE_REPLAY_VERSION = "crucible-oracle-replay/v1"


def replay_observations(bundle: dict[str, Any]) -> dict[str, Any]:
    """Recompute observations only when the bundle's oracle identity matches.

    The outcome is agreement with the historical per-property statuses. It is
    not an assessment of skill quality, provider authenticity, or repair
    acceptance. No provider or model executor is constructed.
    """
    return _run(bundle, mode="PINNED_REPLAY")


def reevaluate_observations(bundle: dict[str, Any]) -> dict[str, Any]:
    """Explicitly re-evaluate complete retained responses with today's oracle."""
    return _run(bundle, mode="REEVALUATION")


def _run(bundle: dict[str, Any], *, mode: str) -> dict[str, Any]:
    sealed = validate_bundle(bundle)
    current = oracle_identity()
    recorded = sealed["oracle"]
    same_oracle = recorded == current
    readiness = replay_readiness(sealed)

    result: dict[str, Any] = {
        "schema_version": ORACLE_REPLAY_VERSION,
        "mode": mode,
        "source_bundle_version": sealed["schema_version"],
        "source_bundle_digest": sealed["bundle_digest"],
        "recorded_oracle": recorded,
        "applied_oracle": current,
        "recorded_oracle_matches_installed": same_oracle,
        "evidence_complete": readiness["evidence_complete"],
        "incomplete_variants": readiness["incomplete_variants"],
        "outcome": "NOT_REPLAYABLE",
        "runs": [],
    }

    if mode == "PINNED_REPLAY" and not same_oracle:
        result["reason"] = "recorded oracle identity does not match installed trusted oracle"
    elif not readiness["evidence_complete"]:
        result["reason"] = "bundle evidence is incomplete; observations were not recomputed"
    else:
        result["runs"] = [
            _replay_run(sealed, run)
            for run in sealed["runs"]
        ]
        after = oracle_identity()
        result["applied_oracle_after"] = after
        if after != current:
            result["outcome"] = "ORACLE_DRIFT"
            result["reason"] = "installed oracle identity changed during replay"
        else:
            all_match = all(run["matches_recorded_observations"] for run in result["runs"])
            if mode == "PINNED_REPLAY":
                result["outcome"] = "MATCH" if all_match else "DIVERGED"
            else:
                result["outcome"] = "REEVALUATED_MATCH" if all_match else "REEVALUATED_DIVERGED"

    result["result_digest"] = digest_payload(result)
    return result


def _replay_run(bundle: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    if bundle["schema_version"] == CAPTURE_REPLAY_VERSION:
        _, response = capture_projection(run["capture"])
    else:
        response = run["response"]

    recomputed = behavioral.run_property_oracle(response["output"], bundle["task"]["properties"])
    recorded_statuses = {
        observation["property_id"]: observation["status"]
        for observation in run["observations"]
    }
    recomputed_statuses = {
        observation["property_id"]: observation["status"]
        for observation in recomputed
    }
    property_results = [
        {
            "property_id": prop["property_id"],
            "recorded_status": recorded_statuses[prop["property_id"]],
            "recomputed_status": recomputed_statuses[prop["property_id"]],
            "matches": recorded_statuses[prop["property_id"]]
            == recomputed_statuses[prop["property_id"]],
        }
        for prop in bundle["task"]["properties"]
    ]
    return {
        "variant_id": run["variant_id"],
        "matches_recorded_observations": all(item["matches"] for item in property_results),
        "properties": property_results,
    }

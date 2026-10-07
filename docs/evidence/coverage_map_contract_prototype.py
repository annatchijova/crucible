"""Validator-only prototype for a versioned rule/check relation artifact.

This is evidence code, not a production API. It validates structure, source
binding, references, and provenance labels; it cannot establish that a link is
semantically correct or authenticate the person who authored a declaration.

Run from the repository root with:
    .venv/bin/python docs/evidence/coverage_map_contract_prototype.py
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from crucible.auditor import audit_corpus
from crucible.compiler import compile_corpus
from crucible.ir import digest_payload


SCHEMA_VERSION = "crucible-coverage-map/v1"
_TOP_LEVEL_KEYS = {
    "schema_version",
    "source_ir_digest",
    "source_audit_digest",
    "entries",
    "coverage_map_digest",
}
_ENTRY_KEYS = {
    "skill",
    "rule_id",
    "check_id",
    "relation_status",
    "provenance",
    "evidence_ref",
}
_STATUS_PROVENANCE = {
    "DECLARED": {"AUTHOR_SOURCE"},
    "PROPOSED": {"DETERMINISTIC", "MODEL"},
}
_MAX_ENTRIES = 10_000
_MAX_TEXT_LENGTH = 500


def seal_map(
    ir: dict[str, Any],
    audit: dict[str, Any],
    entries: list[dict[str, str]],
) -> dict[str, Any]:
    """Add a reproducible digest; this is integrity metadata, not a signature."""
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_ir_digest": ir["artifact_digest"],
        "source_audit_digest": audit["audit_digest"],
        "entries": entries,
    }
    return {**body, "coverage_map_digest": digest_payload(body)}


def validate_map(
    relation_map: Any,
    ir: dict[str, Any],
    audit: dict[str, Any],
) -> None:
    """Raise ValueError at the boundary on malformed or stale map input."""
    if not isinstance(relation_map, dict):
        raise ValueError("coverage map must be an object")
    if set(relation_map) != _TOP_LEVEL_KEYS:
        raise ValueError("coverage map has missing or unknown top-level keys")
    if relation_map["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported coverage map schema_version")
    if not isinstance(ir, dict) or not isinstance(audit, dict):
        raise ValueError("source IR and audit must be objects")
    if ir.get("schema_version") != "skill-ir/v1":
        raise ValueError("unsupported source IR schema_version")
    if not isinstance(ir.get("skills"), list):
        raise ValueError("source IR skills must be a list")
    try:
        ir_body = {key: value for key, value in ir.items() if key != "artifact_digest"}
        audit_body = {key: value for key, value in audit.items() if key != "audit_digest"}
        if ir.get("artifact_digest") != digest_payload(ir_body):
            raise ValueError("source IR artifact_digest is invalid")
        if audit.get("audit_digest") != digest_payload(audit_body):
            raise ValueError("source audit audit_digest is invalid")
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("source "):
            raise
        raise ValueError("source artifacts are not canonical JSON data") from exc
    if audit.get("audit_version") != "crucible-audit/v1":
        raise ValueError("unsupported source audit version")
    if audit.get("input_artifact_digest") != ir.get("artifact_digest"):
        raise ValueError("audit is not bound to the supplied IR artifact")
    if relation_map["source_ir_digest"] != ir.get("artifact_digest"):
        raise ValueError("coverage map source_ir_digest does not match IR")
    if relation_map["source_audit_digest"] != audit.get("audit_digest"):
        raise ValueError("coverage map source_audit_digest does not match audit")

    entries = relation_map["entries"]
    if not isinstance(entries, list) or len(entries) > _MAX_ENTRIES:
        raise ValueError("coverage map entries must be a bounded list")

    body = {key: relation_map[key] for key in _TOP_LEVEL_KEYS - {"coverage_map_digest"}}
    try:
        expected_map_digest = digest_payload(body)
    except (TypeError, ValueError) as exc:
        raise ValueError("coverage map is not canonical JSON data") from exc
    if relation_map["coverage_map_digest"] != expected_map_digest:
        raise ValueError("coverage_map_digest does not match canonical payload")

    skills: dict[str, dict[str, set[str]]] = {}
    for index, skill in enumerate(ir["skills"]):
        if not isinstance(skill, dict) or not isinstance(skill.get("identity"), dict):
            raise ValueError(f"source IR skill {index} has invalid structure")
        name = skill["identity"].get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"source IR skill {index} has invalid identity name")
        if name in skills:
            raise ValueError(f"duplicate skill identity in IR: {name!r}")
        if not isinstance(skill.get("rules"), list) or not isinstance(skill.get("checks"), list):
            raise ValueError(f"source IR skill {name!r} has invalid rule/check lists")
        if any(not isinstance(item, dict) or not isinstance(item.get("id"), str)
               for item in skill["rules"] + skill["checks"]):
            raise ValueError(f"source IR skill {name!r} has malformed rule/check IDs")
        rule_ids = [item["id"] for item in skill["rules"]]
        check_ids = [item["id"] for item in skill["checks"]]
        if len(rule_ids) != len(set(rule_ids)) or len(check_ids) != len(set(check_ids)):
            raise ValueError(f"source IR skill {name!r} has duplicate rule/check IDs")
        skills[name] = {"rules": set(rule_ids), "checks": set(check_ids)}

    seen: set[tuple[str, str, str]] = set()
    sort_keys: list[tuple[str, str, str]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
            raise ValueError(f"entry {index} has missing or unknown keys")
        for field in ("skill", "rule_id", "check_id", "relation_status",
                      "provenance", "evidence_ref"):
            value = entry[field]
            if not isinstance(value, str) or not value or len(value) > _MAX_TEXT_LENGTH:
                raise ValueError(f"entry {index} has invalid {field}")
        allowed_provenance = _STATUS_PROVENANCE.get(entry["relation_status"])
        if allowed_provenance is None:
            raise ValueError(f"entry {index} has unsupported relation_status")
        if entry["provenance"] not in allowed_provenance:
            raise ValueError(f"entry {index} has incompatible provenance/status")

        skill_name = entry["skill"]
        if skill_name not in skills:
            raise ValueError(f"entry {index} references unknown skill")
        if entry["rule_id"] not in skills[skill_name]["rules"]:
            raise ValueError(f"entry {index} references unknown rule_id")
        if entry["check_id"] not in skills[skill_name]["checks"]:
            raise ValueError(f"entry {index} references unknown check_id")

        key = (skill_name, entry["rule_id"], entry["check_id"])
        if key in seen:
            raise ValueError(f"entry {index} duplicates or conflicts with a relation")
        seen.add(key)
        sort_keys.append(key)
    if sort_keys != sorted(sort_keys):
        raise ValueError("coverage map entries must be sorted by relation key")


def _fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    with TemporaryDirectory(prefix="crucible-coverage-map-") as temp:
        root = Path(temp)
        skill = root / "fixture"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\n"
            "name: coverage-map-fixture\n"
            "description: Synthetic validator fixture.\n"
            "---\n\n"
            "The request MUST be idempotent.\n\n"
            "The response status MUST be exactly 200.\n\n"
            "## Checks\n\n"
            "- Verify idempotency by submitting the request twice and comparing state.\n"
            "- The response status is exactly 200.\n",
            encoding="utf-8",
            newline="\n",
        )
        ir = compile_corpus(root)
        audit = audit_corpus(ir)
    return ir, audit


def main() -> None:
    ir, audit = _fixture()
    skill = ir["skills"][0]
    base_entry = {
        "skill": skill["identity"]["name"],
        "rule_id": skill["rules"][0]["id"],
        "check_id": skill["checks"][0]["id"],
        "relation_status": "DECLARED",
        "provenance": "AUTHOR_SOURCE",
        "evidence_ref": "SKILL.md#checks/item-1",
    }
    deterministic_entry = {
        **base_entry,
        "check_id": skill["checks"][1]["id"],
        "relation_status": "PROPOSED",
        "provenance": "DETERMINISTIC",
        "evidence_ref": "local-token-candidate/score=1/5",
    }
    model_entry = {
        **base_entry,
        "rule_id": skill["rules"][1]["id"],
        "check_id": skill["checks"][1]["id"],
        "relation_status": "PROPOSED",
        "provenance": "MODEL",
        "evidence_ref": "confirmation-observation/item-1",
    }
    scenarios: list[
        tuple[str, dict[str, Any], bool, str, dict[str, Any], dict[str, Any]]
    ] = []

    def add(
        name: str,
        relation_map: dict[str, Any],
        accepted: bool,
        expected_error: str,
        case_ir: dict[str, Any] | None = None,
        case_audit: dict[str, Any] | None = None,
    ) -> None:
        scenarios.append((
            name,
            relation_map,
            accepted,
            expected_error,
            ir if case_ir is None else case_ir,
            audit if case_audit is None else case_audit,
        ))

    valid = seal_map(ir, audit, [base_entry])
    add("valid_declared_relation", valid, True, "")
    add(
        "valid_deterministic_proposal",
        seal_map(ir, audit, [deterministic_entry]),
        True,
        "",
    )
    add("valid_model_proposal", seal_map(ir, audit, [model_entry]), True, "")
    add(
        "sorted_mixed_provenance",
        seal_map(ir, audit, [base_entry, deterministic_entry, model_entry]),
        True,
        "",
    )

    stale_ir = {**valid, "source_ir_digest": "sha256:stale"}
    stale_ir_body = {key: stale_ir[key] for key in _TOP_LEVEL_KEYS - {"coverage_map_digest"}}
    stale_ir["coverage_map_digest"] = digest_payload(stale_ir_body)
    add("stale_ir_binding", stale_ir, False, "source_ir_digest")

    stale_audit = {**valid, "source_audit_digest": "sha256:stale"}
    stale_audit_body = {key: stale_audit[key] for key in _TOP_LEVEL_KEYS - {"coverage_map_digest"}}
    stale_audit["coverage_map_digest"] = digest_payload(stale_audit_body)
    add("stale_audit_binding", stale_audit, False, "source_audit_digest")

    tampered_ir = {**ir, "skills": []}
    add(
        "tampered_ir_digest",
        valid,
        False,
        "source IR artifact_digest",
        case_ir=tampered_ir,
    )

    tampered_audit = {**audit, "findings": []}
    add(
        "tampered_audit_digest",
        valid,
        False,
        "source audit audit_digest",
        case_audit=tampered_audit,
    )

    unknown_rule_entry = {**base_entry, "rule_id": "rule-9999"}
    add("unknown_rule_id", seal_map(ir, audit, [unknown_rule_entry]), False, "unknown rule_id")

    unknown_check_entry = {**base_entry, "check_id": "check-9999"}
    add("unknown_check_id", seal_map(ir, audit, [unknown_check_entry]), False, "unknown check_id")

    duplicate_entry = {**base_entry}
    add("duplicate_relation", seal_map(ir, audit, [base_entry, duplicate_entry]), False, "duplicates")

    adjudicated_entry = {**base_entry, "relation_status": "ADJUDICATED", "provenance": "HUMAN"}
    add("unauthenticated_adjudication", seal_map(ir, audit, [adjudicated_entry]), False, "unsupported relation_status")

    provenance_mismatch = {**base_entry, "provenance": "MODEL"}
    add("declared_model_relation", seal_map(ir, audit, [provenance_mismatch]), False, "incompatible provenance/status")

    tampered = {**valid, "entries": []}
    add("tampered_map_digest", tampered, False, "coverage_map_digest")

    results: list[dict[str, Any]] = []
    for name, relation_map, expected_acceptance, expected_error, case_ir, case_audit in scenarios:
        try:
            validate_map(relation_map, case_ir, case_audit)
            accepted, observed_error = True, ""
        except ValueError as exc:
            accepted, observed_error = False, str(exc)
        passed = accepted == expected_acceptance and expected_error in observed_error
        results.append({
            "name": name,
            "expected": "ACCEPT" if expected_acceptance else "REJECT",
            "observed": "ACCEPT" if accepted else "REJECT",
            "error": observed_error,
            "harness_pass": passed,
        })

    output = {
        "experiment": "coverage-map-contract-prototype/v1",
        "scope": "structural validator only; no semantic link judgment",
        "source_ir_digest": ir["artifact_digest"],
        "source_audit_digest": audit["audit_digest"],
        "case_count": len(results),
        "all_expectations_met": all(item["harness_pass"] for item in results),
        "cases": results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    if not output["all_expectations_met"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

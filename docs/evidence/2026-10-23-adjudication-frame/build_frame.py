"""Build a stratified, reproducible adjudication frame over audit findings.

"What proportion of candidate findings survive adjudication?" needs three
things this script provides and one it cannot.

It provides a *frame*: which findings a reviewer is asked to judge, chosen
before any judging, bound to the corpus and audit digests they came from, and
reproducible by anyone who recompiles the same commit. Selection inside a
stratum is by SHA-256 of a stable finding key, so it is deterministic and
unrelated to whether the finding is correct -- reproducible pseudo-random
rather than a documented probability sample.

It distinguishes a **census** stratum, where the target covers the whole
population and the adjudicated proportion is exact, from a **sample** stratum,
where it does not and the proportion is an estimate this frame cannot attach
an interval to.

It carries no expected label, no model opinion and no prior adjudication, for
the same reason the coverage packet carries none.

What it cannot provide is the judgement. A frame is not evidence about
precision until a reviewer fills it in, and filling it in spends the frame:
findings adjudicated here may be used to report precision and must not be used
to tune the detector, which would consume the held-out corpus.

Usage:
    python build_frame.py <out-dir> [per-stratum-target] [corpus-root=corpus_id ...]
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from crucible.auditor import audit_corpus
from crucible.compiler import compile_corpus
from crucible.corpus_provenance import build_provenance, validate_provenance
from crucible.ir import digest_payload

FRAME_VERSION = "adjudication-frame/v1"
DEFAULT_TARGET = 10

LIMITATION = (
    "a frame is not evidence about precision; it records which findings a "
    "reviewer was asked to judge, chosen before any judging. Selection inside "
    "a stratum is deterministic pseudo-random, not a documented probability "
    "sample, so a sample stratum's adjudicated proportion is an estimate "
    "without an interval. Findings adjudicated through this frame may be used "
    "to report precision and must not be used to tune the detector."
)


def stable_key(corpus_id: str, finding: dict) -> str:
    """Identify a finding by what it points at, not by its ordinal id.

    Finding ids are positional and shift whenever the auditor changes, so they
    cannot anchor a selection that must survive a re-audit.
    """
    span = finding.get("source_span") or {}
    return "|".join(str(part) for part in (
        corpus_id, finding["class"], finding["skill"], finding["source_path"],
        finding["rule_id"], span.get("line"), span.get("column"),
    ))


def selector(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def corpus_entry(root: str, corpus_id: str) -> tuple[dict, dict, list[dict]]:
    commit = subprocess.run(
        ["git", "-C", root, "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if subprocess.run(["git", "-C", root, "status", "--porcelain"],
                      capture_output=True, text=True, check=True).stdout:
        raise SystemExit(f"{corpus_id}: worktree is not clean; refusing to build a frame")
    ir = compile_corpus(root)
    audit = audit_corpus(ir)
    provenance = validate_provenance(build_provenance(
        ir, corpus_id=corpus_id, role="HELDOUT_SEALED",
        repository=_remote(root), commit=commit,
    ))
    digests = {
        skill["identity"]["source_path"]: skill["identity"]["content_digest"]
        for skill in ir["skills"]
    }
    return provenance, audit, digests


def _remote(root: str) -> str:
    return subprocess.run(
        ["git", "-C", root, "remote", "get-url", "origin"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def build(targets: list[tuple[str, str]], per_stratum: int) -> tuple[dict, dict]:
    corpora, strata, private = [], [], {}
    for root, corpus_id in targets:
        provenance, audit, digests = corpus_entry(root, corpus_id)
        corpora.append({
            "corpus_id": corpus_id,
            "provenance_digest": provenance["provenance_digest"],
            "manifest_digest": provenance["manifest_digest"],
            "audit_digest": audit["audit_digest"],
            "audit_version": audit["audit_version"],
            "skill_count": provenance["skill_count"],
            "findings_total": audit["summary"]["total"],
            "commit": provenance["source_reference"]["commit"],
        })
        by_class: dict[str, list[dict]] = {}
        for finding in audit["findings"]:
            by_class.setdefault(finding["class"], []).append(finding)
        for finding_class in sorted(by_class):
            population = by_class[finding_class]
            ranked = sorted(
                population, key=lambda f: selector(stable_key(corpus_id, f))
            )
            chosen = ranked[:per_stratum]
            census = len(chosen) == len(population)
            strata.append({
                "corpus_id": corpus_id,
                "finding_class": finding_class,
                "population": len(population),
                "selected": len(chosen),
                "coverage": "CENSUS" if census else "SAMPLE",
                "selection": [{
                    "finding_id": f["id"],
                    "skill": f["skill"],
                    "source_path": f["source_path"],
                    "source_span": f["source_span"],
                    "source_file_digest": digests.get(f["source_path"]),
                    "rule_id": f["rule_id"],
                    "selector": selector(stable_key(corpus_id, f))[:16],
                } for f in chosen],
            })
            private[f"{corpus_id}/{finding_class}"] = [{
                "finding_id": f["id"],
                "skill": f["skill"],
                "source_path": f["source_path"],
                "source_span": f["source_span"],
                "evidence": f["evidence"],
                "limitation": f["limitation"],
                "violated_invariant": f["violated_invariant"],
                "epistemic_status": f["epistemic_status"],
            } for f in chosen]
    frame = {
        "schema_version": FRAME_VERSION,
        "annotation_state": "UNLABELED",
        "stratification": {
            "key": "corpus_id and finding class",
            "selector": "sha256 of corpus_id|class|skill|source_path|rule_id|line|column",
            "per_stratum_target": per_stratum,
        },
        "corpora": corpora,
        "strata": strata,
        "selected_total": sum(s["selected"] for s in strata),
        "population_total": sum(s["population"] for s in strata),
        "census_strata": sum(1 for s in strata if s["coverage"] == "CENSUS"),
        "sample_strata": sum(1 for s in strata if s["coverage"] == "SAMPLE"),
        "limitation": LIMITATION,
    }
    frame["frame_digest"] = digest_payload(frame)
    return frame, private


RESPONSE_VERSION = "adjudication-response/v1"

# CONFIRMED and REJECTED are the two real outcomes; UNRESOLVED exists so a
# reviewer is never forced into a binary answer, matching the three-state rule
# in CLAUDE.md section 5.3 and the coverage rubric's own UNRESOLVED.
OUTCOMES = ("CONFIRMED", "REJECTED", "UNRESOLVED")


def response_template(frame: dict) -> dict:
    """One blank row per selected finding, bound to the frame it came from."""
    return {
        "schema_version": RESPONSE_VERSION,
        "frame_schema_version": FRAME_VERSION,
        "frame_digest": frame["frame_digest"],
        "reviewer_label": None,
        "authenticity_status": "UNVERIFIED",
        "allowed_outcomes": list(OUTCOMES),
        "assessments": [
            {
                "corpus_id": stratum["corpus_id"],
                "finding_class": stratum["finding_class"],
                "finding_id": item["finding_id"],
                "selector": item["selector"],
                "outcome": None,
                "rationale": None,
                "source_quote": None,
            }
            for stratum in frame["strata"] for item in stratum["selection"]
        ],
    }


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    out = Path(sys.argv[1])
    per_stratum = int(sys.argv[2]) if sys.argv[2].isdigit() else DEFAULT_TARGET
    rest = sys.argv[3:] if sys.argv[2].isdigit() else sys.argv[2:]
    targets = []
    for spec in rest:
        root, _, corpus_id = spec.partition("=")
        targets.append((str(Path(root).resolve()), corpus_id or Path(root).name))
    if not targets:
        raise SystemExit("at least one corpus-root=corpus_id is required")
    frame, private = build(targets, per_stratum)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "frame.json").open("w") as fh:
        json.dump(frame, fh, indent=1, sort_keys=True)
        fh.write("\n")
    # Reviewer material carries auditor evidence strings, which can echo
    # extracted source tokens, so it is written beside the frame and is not
    # for commit until per-skill licensing is cleared.
    with (out / "reviewer-material.PRIVATE.json").open("w") as fh:
        json.dump(private, fh, indent=1, sort_keys=True)
        fh.write("\n")
    with (out / "response-template.json").open("w") as fh:
        json.dump(response_template(frame), fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(json.dumps({
        "frame_digest": frame["frame_digest"],
        "selected_total": frame["selected_total"],
        "population_total": frame["population_total"],
        "census_strata": frame["census_strata"],
        "sample_strata": frame["sample_strata"],
        "per_stratum_target": per_stratum,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

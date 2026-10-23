"""Build a blind false-negative frame: skills to read without seeing findings.

The precision frame asks whether an emitted finding is real. This asks the
opposite and harder question: when Crucible says nothing about a skill, is the
skill actually clean? On the held-out corpora Crucible is silent on 54% and
25% of skills respectively, so that is where a missed defect would hide.

Three design constraints follow, and the script enforces all three.

**Blindness.** A reviewer who knows a skill produced zero findings will read
it differently. So the reviewer packet carries only corpus, path and content
digest; the stratification, the finding counts and the bucket live in the
frame, which is written to a private path and is not handed over. The packet
is ordered by a different hash than the one used to select, so packet order
leaks nothing about which bucket a skill came from.

**No anchoring to Crucible's ontology.** The reviewer reports defects in their
own words first. Mapping a report onto a finding class happens afterward, as a
separate recorded step. Handing over the 30 class names up front would bias
the review toward exactly the defects Crucible already detects, which
understates the quantity being measured.

**A commitment, not a promise.** The frame digest is committed before any
review, so the stratification and allocation cannot be chosen after the
results are in. The frame content is published once the review is frozen.

Usage:
    python build_fn_frame.py <private-out-dir> <committed-out-dir> [total]
        [corpus-root=corpus_id ...]
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
from crucible.ir import digest_payload

FRAME_VERSION = "false-negative-frame/v1"
PACKET_VERSION = "false-negative-packet/v1"
RESPONSE_VERSION = "false-negative-response/v1"
COMMITMENT_VERSION = "false-negative-commitment/v1"

BUCKETS = ("0", "1-2", "3-5", "6+")

# Weighted toward the silent bucket because that is the question. Fixed here so
# it is committed rather than chosen once results are visible.
DEFAULT_ALLOCATION = {"0": 10, "1-2": 8, "3-5": 4, "6+": 2}
DEFAULT_TOTAL = 24

FRAME_LIMITATION = (
    "this is a discovery instrument, not an estimator. A sample this size "
    "supports a lower bound of the form 'at least N missed defects of M kinds "
    "exist in the reviewed skills', and supports no false-negative rate, "
    "recall figure or interval. Reviewing these skills spends them: they may "
    "be used to report missed defects and must not be used to tune the "
    "detector, which would consume the held-out corpus."
)


def bucket_of(count: int) -> str:
    if count == 0:
        return "0"
    if count <= 2:
        return "1-2"
    if count <= 5:
        return "3-5"
    return "6+"


def selector(prefix: str, key: str) -> str:
    return hashlib.sha256(f"{prefix}|{key}".encode("utf-8")).hexdigest()


def corpus_state(root: str, corpus_id: str) -> dict:
    commit = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    if subprocess.run(["git", "-C", root, "status", "--porcelain"],
                      capture_output=True, text=True, check=True).stdout:
        raise SystemExit(f"{corpus_id}: worktree is not clean; refusing to build a frame")
    repository = subprocess.run(["git", "-C", root, "remote", "get-url", "origin"],
                                capture_output=True, text=True, check=True).stdout.strip()
    ir = compile_corpus(root)
    audit = audit_corpus(ir)
    counts: dict[str, int] = {}
    for finding in audit["findings"]:
        counts[finding["source_path"]] = counts.get(finding["source_path"], 0) + 1
    skills = [{
        "corpus_id": corpus_id,
        "skill": skill["identity"]["name"],
        "source_path": skill["identity"]["source_path"],
        "content_digest": skill["identity"]["content_digest"],
        "finding_count": counts.get(skill["identity"]["source_path"], 0),
    } for skill in ir["skills"]]
    for entry in skills:
        entry["bucket"] = bucket_of(entry["finding_count"])
    return {
        "corpus_id": corpus_id,
        "repository": repository,
        "commit": commit,
        "audit_digest": audit["audit_digest"],
        "audit_version": audit["audit_version"],
        "skill_count": len(skills),
        "findings_total": audit["summary"]["total"],
        "skills": skills,
    }


def allocate(states: list[dict], total: int) -> dict[str, int]:
    """Scale the default allocation to the requested total, keeping its shape."""
    base_total = sum(DEFAULT_ALLOCATION.values())
    scaled = {b: max(1, DEFAULT_ALLOCATION[b] * total // base_total) for b in BUCKETS}
    available = {
        b: sum(1 for s in states for k in s["skills"] if k["bucket"] == b)
        for b in BUCKETS
    }
    return {b: min(scaled[b], available[b]) for b in BUCKETS}


def build(states: list[dict], total: int) -> tuple[dict, dict]:
    allocation = allocate(states, total)
    strata, chosen = [], []
    for bucket in BUCKETS:
        population = [k for s in states for k in s["skills"] if k["bucket"] == bucket]
        ranked = sorted(population, key=lambda k: selector(
            "select", f"{k['corpus_id']}|{k['source_path']}|{k['content_digest']}"))
        picked = ranked[:allocation[bucket]]
        chosen.extend(picked)
        strata.append({
            "bucket": bucket,
            "population": len(population),
            "selected": len(picked),
            "per_corpus_population": {
                s["corpus_id"]: sum(1 for k in s["skills"] if k["bucket"] == bucket)
                for s in states
            },
            "per_corpus_selected": {
                s["corpus_id"]: sum(1 for k in picked if k["corpus_id"] == s["corpus_id"])
                for s in states
            },
            "selection": [{
                "corpus_id": k["corpus_id"],
                "skill": k["skill"],
                "source_path": k["source_path"],
                "content_digest": k["content_digest"],
                "finding_count": k["finding_count"],
            } for k in picked],
        })
    frame = {
        "schema_version": FRAME_VERSION,
        "annotation_state": "UNLABELED",
        "corpora": [{k: v for k, v in s.items() if k != "skills"} for s in states],
        "stratification": {
            "key": "count of findings the auditor emitted for the skill",
            "buckets": list(BUCKETS),
            "allocation": allocation,
            "selector": "sha256 of 'select|corpus_id|source_path|content_digest'",
            "rationale": "weighted toward the zero-finding bucket, which is the "
                         "condition under test",
        },
        "strata": strata,
        "selected_total": len(chosen),
        "limitation": FRAME_LIMITATION,
    }
    frame["frame_digest"] = digest_payload(frame)
    packet = reviewer_packet(states, chosen)
    return frame, packet


def reviewer_packet(states: list[dict], chosen: list[dict]) -> dict:
    """Skills to read, carrying nothing about what the auditor said.

    Ordered by a different hash prefix than the selector, so position in the
    packet reveals nothing about which bucket a skill came from.
    """
    items = sorted(chosen, key=lambda k: selector(
        "present", f"{k['corpus_id']}|{k['source_path']}|{k['content_digest']}"))
    return {
        "schema_version": PACKET_VERSION,
        "annotation_state": "UNLABELED",
        "instruction": "Read each skill from a clean checkout of its corpus at "
                       "the recorded commit and verify the content digest "
                       "before reviewing it. Record defects in your own words. "
                       "Reporting nothing for a skill is a valid and expected "
                       "outcome.",
        "corpora": [{
            "corpus_id": s["corpus_id"],
            "repository": s["repository"],
            "commit": s["commit"],
        } for s in states],
        "items": [{
            "item_index": index,
            "corpus_id": k["corpus_id"],
            "source_path": k["source_path"],
            "content_digest": k["content_digest"],
        } for index, k in enumerate(items)],
    }


def response_template(packet: dict) -> dict:
    return {
        "schema_version": RESPONSE_VERSION,
        "packet_schema_version": PACKET_VERSION,
        "packet_digest": digest_payload(packet),
        "reviewer_label": None,
        "authenticity_status": "UNVERIFIED",
        "reviews": [{
            "item_index": item["item_index"],
            "corpus_id": item["corpus_id"],
            "source_path": item["source_path"],
            "digest_verified": None,
            "read_completely": None,
            "defects": [],
        } for item in packet["items"]],
        "defect_shape": {
            "description": "the defect in the reviewer's own words",
            "line_start": "first source line the defect rests on",
            "line_end": "last source line the defect rests on",
            "quote": "text copied from the skill",
            "why_it_is_a_defect": "what following this instruction would cause",
        },
    }


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    private, committed = Path(sys.argv[1]), Path(sys.argv[2])
    total = int(sys.argv[3]) if sys.argv[3].isdigit() else DEFAULT_TOTAL
    rest = sys.argv[4:] if sys.argv[3].isdigit() else sys.argv[3:]
    targets = []
    for spec in rest:
        root, _, corpus_id = spec.partition("=")
        targets.append((str(Path(root).resolve()), corpus_id or Path(root).name))
    if not targets:
        raise SystemExit("at least one corpus-root=corpus_id is required")

    states = [corpus_state(root, corpus_id) for root, corpus_id in targets]
    frame, packet = build(states, total)
    template = response_template(packet)
    commitment = {
        "schema_version": COMMITMENT_VERSION,
        "frame_digest": frame["frame_digest"],
        "packet_digest": template["packet_digest"],
        "selected_total": frame["selected_total"],
        "allocation": frame["stratification"]["allocation"],
        "corpora": [{
            "corpus_id": c["corpus_id"], "commit": c["commit"],
            "audit_digest": c["audit_digest"], "skill_count": c["skill_count"],
            "findings_total": c["findings_total"],
        } for c in frame["corpora"]],
        "note": "the frame content is withheld until the review is frozen, so "
                "the reviewer cannot learn which skills produced no findings. "
                "This digest commits to the stratification and allocation "
                "before any review exists.",
    }
    commitment["commitment_digest"] = digest_payload(commitment)

    private.mkdir(parents=True, exist_ok=True)
    committed.mkdir(parents=True, exist_ok=True)
    _write(private / "frame.PRIVATE.json", frame)
    _write(committed / "reviewer-packet.json", packet)
    _write(committed / "response-template.json", template)
    _write(committed / "commitment.json", commitment)
    print(json.dumps({
        "frame_digest": frame["frame_digest"],
        "packet_digest": template["packet_digest"],
        "commitment_digest": commitment["commitment_digest"],
        "selected_total": frame["selected_total"],
        "allocation": frame["stratification"]["allocation"],
        "strata": [{k: v for k, v in s.items() if k != "selection"}
                   for s in frame["strata"]],
    }, indent=2, sort_keys=True))


def _write(path: Path, payload: dict) -> None:
    with path.open("w") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    main()

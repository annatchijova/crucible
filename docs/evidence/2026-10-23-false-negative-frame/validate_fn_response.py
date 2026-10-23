"""Validate a blind review response, then compare it against the auditor.

Two modes, deliberately separate, because the order matters. Validation needs
only the reviewer packet, so it can run while the frame is still sealed.
Comparison needs the frame and must run only after the response is frozen.

The comparison implements PROTOCOL.md's frozen rule and nothing else: strict
span containment, no line tolerance in either direction. Padding spans would
raise match counts and so lower apparent false negatives, which is the
direction of the result being measured.

Nothing here confirms a false negative. It separates candidates, and says so.

Usage:
    python validate_fn_response.py <reviewer-packet.json> <response.json>
    python validate_fn_response.py <reviewer-packet.json> <response.json> \
        --compare <frame.PRIVATE.json> <corpus-root=corpus_id ...>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from crucible.auditor import audit_corpus
from crucible.compiler import compile_corpus
from crucible.ir import digest_payload

PACKET_VERSION = "false-negative-packet/v1"
RESPONSE_VERSION = "false-negative-response/v1"
FRAME_VERSION = "false-negative-frame/v1"

DEFECT_FIELDS = ("description", "line_start", "line_end", "quote",
                 "why_it_is_a_defect")

CANDIDATE_LIMITATION = (
    "every row below is a candidate. Span overlap is not proof that a reported "
    "defect and a finding describe the same problem, and an unmatched reported "
    "defect is a candidate false negative that becomes a missed defect only "
    "after a recorded adjudication. No rate, recall figure or interval may be "
    "derived from these counts."
)


def fail(message: str) -> None:
    raise SystemExit(f"error: {message}")


def validate(packet_path: Path, response_path: Path) -> tuple[dict, dict]:
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    if packet.get("schema_version") != PACKET_VERSION:
        fail(f"{packet_path.name}: unsupported packet schema")
    response = json.loads(response_path.read_text(encoding="utf-8"))
    if response.get("schema_version") != RESPONSE_VERSION:
        fail(f"{response_path.name}: unsupported response schema")
    if response.get("packet_digest") != digest_payload(packet):
        fail(f"{response_path.name}: response is not bound to this packet digest")
    label = response.get("reviewer_label")
    if not isinstance(label, str) or not label.strip():
        fail(f"{response_path.name}: reviewer_label is required")
    if response.get("authenticity_status") != "UNVERIFIED":
        fail(f"{response_path.name}: no reviewer trust root exists; status must "
             f"stay UNVERIFIED")

    reviews = response.get("reviews")
    if not isinstance(reviews, list):
        fail(f"{response_path.name}: reviews must be a list")
    expected = [(i["item_index"], i["corpus_id"], i["source_path"])
                for i in packet["items"]]
    observed = [(r.get("item_index"), r.get("corpus_id"), r.get("source_path"))
                for r in reviews]
    if observed != expected:
        fail(f"{response_path.name}: reviews do not match the packet items in order")

    for review in reviews:
        where = f"{response_path.name}: item {review['item_index']}"
        for flag in ("digest_verified", "read_completely"):
            if type(review.get(flag)) is not bool:
                fail(f"{where}: {flag} must be stated as true or false")
        if review["digest_verified"] is False and review["defects"]:
            fail(f"{where}: defects reported against an unverified file")
        if not isinstance(review["defects"], list):
            fail(f"{where}: defects must be a list")
        for index, defect in enumerate(review["defects"]):
            spot = f"{where} defect {index}"
            if set(defect) != set(DEFECT_FIELDS):
                fail(f"{spot}: expected exactly {sorted(DEFECT_FIELDS)}")
            for key in ("description", "quote", "why_it_is_a_defect"):
                if not isinstance(defect[key], str) or not defect[key].strip():
                    fail(f"{spot}: {key} is required")
            for key in ("line_start", "line_end"):
                if type(defect[key]) is not int or defect[key] < 1:
                    fail(f"{spot}: {key} must be a line number of 1 or more")
            if defect["line_end"] < defect["line_start"]:
                fail(f"{spot}: line_end precedes line_start")
    return packet, response


def summarize(response: dict) -> dict:
    reviews = response["reviews"]
    read = [r for r in reviews if r["read_completely"] and r["digest_verified"]]
    return {
        "reviewer_label": response["reviewer_label"],
        "items_in_packet": len(reviews),
        "items_fully_read_and_verified": len(read),
        "items_excluded_from_denominators": len(reviews) - len(read),
        "defects_reported": sum(len(r["defects"]) for r in read),
        "items_with_no_defect_reported": sum(1 for r in read if not r["defects"]),
        "authenticity_status": "UNVERIFIED",
    }


def compare(frame: dict, response: dict, roots: dict[str, str]) -> dict:
    if frame.get("schema_version") != FRAME_VERSION:
        fail("unsupported frame schema")
    sealed = {k: v for k, v in frame.items() if k != "frame_digest"}
    if frame.get("frame_digest") != digest_payload(sealed):
        fail("frame digest mismatch; the frame was edited after sealing")

    bucket_of: dict[tuple[str, str], str] = {}
    for stratum in frame["strata"]:
        for item in stratum["selection"]:
            bucket_of[(item["corpus_id"], item["source_path"])] = stratum["bucket"]

    findings: dict[tuple[str, str], list[dict]] = {}
    for corpus in frame["corpora"]:
        corpus_id = corpus["corpus_id"]
        root = roots.get(corpus_id)
        if root is None:
            fail(f"no corpus root given for {corpus_id}")
        audit = audit_corpus(compile_corpus(root))
        if audit["audit_digest"] != corpus["audit_digest"]:
            fail(f"{corpus_id}: audit digest differs from the sealed frame; "
                 f"the corpus or the auditor changed since the frame was built")
        for finding in audit["findings"]:
            findings.setdefault((corpus_id, finding["source_path"]), []).append(finding)

    candidate_matches, candidate_fn, candidate_fp = [], [], []
    per_bucket: dict[str, dict] = {}
    for review in response["reviews"]:
        if not (review["read_completely"] and review["digest_verified"]):
            continue
        key = (review["corpus_id"], review["source_path"])
        bucket = bucket_of.get(key, "UNKNOWN")
        stats = per_bucket.setdefault(bucket, {
            "bucket": bucket, "items_reviewed": 0, "defects_reported": 0,
            "candidate_matches": 0, "candidate_false_negatives": 0,
            "candidate_false_positives": 0,
        })
        stats["items_reviewed"] += 1
        stats["defects_reported"] += len(review["defects"])
        available = findings.get(key, [])
        matched_findings: set[str] = set()
        for index, defect in enumerate(review["defects"]):
            hits = [
                f for f in available
                if (f.get("source_span") or {}).get("line") is not None
                and defect["line_start"] <= f["source_span"]["line"] <= defect["line_end"]
            ]
            if hits:
                matched_findings.update(f["id"] for f in hits)
                stats["candidate_matches"] += 1
                candidate_matches.append({
                    "corpus_id": review["corpus_id"],
                    "source_path": review["source_path"],
                    "bucket": bucket,
                    "defect_index": index,
                    "defect_lines": [defect["line_start"], defect["line_end"]],
                    "finding_ids": sorted(f["id"] for f in hits),
                    "finding_classes": sorted({f["class"] for f in hits}),
                    "disposition": "CANDIDATE_MATCH; needs a recorded "
                                   "adjudication to become MATCHED or "
                                   "DIFFERENT_DEFECT",
                })
            else:
                stats["candidate_false_negatives"] += 1
                candidate_fn.append({
                    "corpus_id": review["corpus_id"],
                    "source_path": review["source_path"],
                    "bucket": bucket,
                    "defect_index": index,
                    "defect_lines": [defect["line_start"], defect["line_end"]],
                    "findings_on_skill": len(available),
                    "disposition": "UNMATCHED_REVIEWER_DEFECT; candidate false "
                                   "negative pending adjudication",
                })
        for finding in available:
            if finding["id"] not in matched_findings:
                stats["candidate_false_positives"] += 1
                candidate_fp.append({
                    "corpus_id": review["corpus_id"],
                    "source_path": review["source_path"],
                    "bucket": bucket,
                    "finding_id": finding["id"],
                    "finding_class": finding["class"],
                    "disposition": "UNMATCHED_FINDING; candidate false positive, "
                                   "cross-checking the precision frame",
                })
    return {
        "frame_digest": frame["frame_digest"],
        "per_bucket": [per_bucket[b] for b in sorted(per_bucket)],
        "candidate_matches": candidate_matches,
        "candidate_false_negatives": candidate_fn,
        "candidate_false_positives": candidate_fp,
        "limitation": CANDIDATE_LIMITATION,
    }


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2:
        raise SystemExit(__doc__)
    packet, response = validate(Path(args[0]), Path(args[1]))
    report = {"validation": summarize(response)}
    if "--compare" in args:
        rest = args[args.index("--compare") + 1:]
        if not rest:
            fail("--compare needs a frame path")
        frame = json.loads(Path(rest[0]).read_text(encoding="utf-8"))
        roots = {}
        for spec in rest[1:]:
            root, _, corpus_id = spec.partition("=")
            roots[corpus_id or Path(root).name] = str(Path(root).resolve())
        report["comparison"] = compare(frame, response, roots)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

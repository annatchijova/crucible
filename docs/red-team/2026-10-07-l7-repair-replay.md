# L7 repair evidence replay — parser boundary review

**Date:** 2026-10-07  **Method:** adversarial local input mutation and regression
test  **Base:** `07edc7b`  **Status:** one parser ambiguity reproduced and fixed;
no provider request made.

## Threat model

- Attacker can provide or alter the JSON bundle before a local reviewer runs
  `--replay-repair-evidence`, and can recompute public SHA-256 seals.
- Attacker cannot change the installed Crucible code or Python runtime during
  replay.
- This review concerns how one local parser interprets the supplied bytes. It
  does not grant the bundle cryptographic authenticity or establish who
  generated provider responses.

## Finding

### L7-JSON-01 — Duplicate member names were accepted by the replay CLI

**Severity:** low  **Epistemic level:** CONFIRMED BY INDUCTION
**Bucket:** parser-boundary integrity ambiguity

Python's default JSON decoder accepts duplicate object member names and keeps
the last value. Before the fix, the replay CLI used `json.load()` directly.
Under the threat model above, inserting a duplicate `provider` member before
the original left the parsed bundle and its valid bundle digest unchanged, so
the CLI returned `MATCH` for ambiguous source bytes. A different consumer that
keeps the first member could read a different provider value. The demonstrated
impact is inconsistent interpretation of the same evidence file; this is not
provider impersonation or a SHA-256 collision.

### Induction record

**Prediction:** a duplicated top-level `provider` key preceding the original
will be silently collapsed by the old CLI parser and the untouched bundle seal
will still verify.

**Reproduction:** `tests/test_repair_evidence_replay.py::test_cli_rejects_duplicate_json_keys`
constructs a valid captured bundle, inserts the duplicate key, and invokes the
CLI. Before the fix, the test failed: exit status was `0` and output status was
`MATCH`.

**Fix:** the CLI now uses the capture contract's strict JSON decoder, which
rejects duplicate names and non-finite constants. It reads at most
`MAX_EVIDENCE_BYTES + 1` before parsing, so a file that grows after a metadata
check cannot bypass the input bound. Malformed, over-limit, or ambiguous input
returns `INVALID_EVIDENCE`.

**Regression evidence:** after the fix, the duplicate-key test expects exit
status `1` and `INVALID_EVIDENCE`. The same reader also rejects deeply nested
JSON, and a separate local test covers that path. No test performs network I/O.

## Discarded vectors and scope limits

- **Resealed changed outcome:** already covered by the replay contract; a
  changed report that is resealed is compared to recomputation and returns
  `DIVERGED`, not `MATCH`.
- **Provider authenticity:** remains outside this bundle's guarantees. A
  self-seal and replay establish consistency of locally retained bytes and
  deterministic recomputation under the pinned local implementation only.
- **Raw journal cross-check:** this CLI validates the embedded bundle, not the
  separate raw-capture files beside it. That limitation remains unchanged.

The finding is closed for this parser boundary after regression verification;
it does not close independent evaluation, provider authenticity, or release
readiness.

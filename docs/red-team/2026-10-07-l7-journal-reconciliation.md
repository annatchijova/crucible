# L7 journal reconciliation — red-team review

**Date:** 2026-10-07  **Method:** local representation mutation and symlink
negative control  **Base:** parser-boundary fix `65d853e`  **Status:** local
reconciliation command implemented and tested; no provider request made.

## Threat model

- Attacker can alter, replace, remove, or add files in an evidence directory
  before an analyst verifies it. They may also replace a raw capture with a
  symlink.
- Attacker cannot modify Crucible code during verification or make the
  verifier's local filesystem calls return forged data.
- The public SHA-256 seals are not secret, so the attacker can recompute them.
  This review checks agreement among local representations, not origin or
  truth of provider responses.

## Finding and design response

### L7-JOURNAL-01 — The bundle verifier did not reconcile its sibling journal

**Severity:** informational under the stated threat model  **Epistemic level:**
CODE FACT  **Bucket:** evidence workflow gap

`verify_repair_evidence(bundle)` validates the embedded event chain and bundle
seal. It receives no directory and therefore cannot establish that
`events.jsonl` or `raw-captures/` still match that embedded representation. An
analyst checking only `bundle.json` could miss a sibling raw file changed after
capture. This is a missing cross-check in the workflow, not a bypass of the
bundle verifier's stated contract.

The new offline command `--verify-repair-evidence-dir JOURNAL_DIR` verifies
the bundle seal, strict JSON structure, ordered event journal, exact raw
capture bytes, and expected raw-file set. It rejects symlinks for the checked
directory entries and uses bounded reads. `MATCH` means local representation
agreement; it does not prove provider origin or prevent later replacement.

## Induction record

**Prediction:** a journal whose embedded bundle remains valid but whose raw
capture gains one byte will be reported as `DIVERGED`; replacing that raw file
with a symlink will not cause the verifier to follow it.

**Reproduction:**

```text
tests/test_repair_evidence_replay.py::test_journal_verification_detects_changed_raw_capture
tests/test_repair_evidence_replay.py::test_journal_verification_rejects_symlinked_raw_capture
```

The first fixture appends a byte to `raw-captures/0000.json` after capture and
expects `DIVERGED / raw-capture-content-differs`. The second replaces that path
with a symlink to an outside file and expects `INVALID_EVIDENCE`. A clean
three-event capture returns `MATCH`; CLI coverage patches the provider boundary
to fail if called and asserts output contains only the summary.

The check also passed on the retained live capture directory
`/tmp/crucible-l7-live-20261007-04`:

```text
./.venv/bin/python -m crucible.cli --verify-repair-evidence-dir /tmp/crucible-l7-live-20261007-04
status=MATCH event_count=3 bundle_digest=sha256:8ec4ca662cc09d743144d3117906d8876bebf91dc33b138e9626ee2093620e2c
```

This was a local read-only verification; no request was sent to Nebius.

## Limits and discarded claims

- A recomputed public digest remains internally consistent but does not prove
  provider identity or model execution.
- This command does not create an external anchor, timestamp, signature, or
  immutable store.
- A successful local check is a point-in-time result; another process with
  filesystem authority can replace the directory afterward.
- These controls do not estimate repair quality or stability.

This closes the local three-representation consistency check for the tested
directory shape. Independent evaluation, external anchoring, and release
verification remain open.

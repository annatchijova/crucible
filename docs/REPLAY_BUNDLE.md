# R2 — replay evidence storage contract

Status: initial Python storage/validation contract implemented; runtime capture
and CLI export are pending. R2 is not closed. R3 oracle execution and repair
acceptance are not implemented by this module.

`src/crucible/replay.py` exposes `validate_bundle`, `dump_bundle`, `load_bundle`
and `replay_readiness`. All are offline and side-effect-free. JSON is limited
to 8,000,000 UTF-8 bytes, 500 variants and 100 task properties. Unknown versions,
unknown fields, duplicate JSON keys and nonfinite JSON constants are rejected.

## Versioned envelope

`crucible-replay-bundle/v1` contains:

| Field | Evidence retained and checked |
|---|---|
| `task`, `task_digest` | Task ID, full prompt and property definitions; canonical digest covers all three |
| `variants` | Unique IDs, exact skill guidance and UTF-8 byte digests; empty baseline guidance allowed |
| `oracle` | Versioned oracle ID and implementation digest; no dynamic code loading |
| `runs` | Exactly one run per variant; complete request, response and historical observations |
| `bundle_digest` | Canonical digest of the whole envelope excluding this field |

Requests contain model, provider, system/user prompts, integer temperature and
max_tokens. This first contract handles exact-guidance experiments: system prompt
equals variant text and user prompt equals task prompt. Provider prompt rewriting,
extra sampling controls and adapters require explicit future contract work, not
silent normalization. No authorization-header or credential field is accepted;
prompts and responses can still contain sensitive text and must be handled as
private evidence unless reviewed for publication.

Responses retain status, raw text and digest, response ID, finish reason,
truncation, usage and error. Unknown optional runtime values are explicit nulls;
missing fields are not invented. Observations retain property ID, status and
evidence, with no duplicates or unknown property IDs.

## Integrity is not acceptance

A valid bundle may archive ERROR, BLOCKED or truncated results. `replay_readiness`
reports evidence as incomplete if any run lacks a complete, nonempty response,
explicit `truncated: false`, `finish_reason: stop`, response ID, usage, or all
property observations. This conservative rule also marks older local results
with missing finish metadata incomplete. It never fabricates provider metadata.

`evidence_complete: true` is **not** an acceptance verdict: it does not establish
oracle availability, observation correctness, provider authenticity or skill
quality. A self-contained digest detects inconsistent/tampered bytes relative to
its seal, not a malicious author who replaces and reseals all evidence. R3 must
match a trusted, pinned oracle implementation and recompute observations.

Historical `crucible-behavioral/v1` artifacts remain untouched and are not accepted
as this bundle. Their task digest did not cover the full property definitions.
Do not reconstruct missing prompts/configuration from today's fixtures and call
that historical evidence. A future importer must either supply independently
retained evidence or explicitly report that conversion cannot be completed.

## Verification and next step

Run `PYTHONPATH=src python3 -m pytest tests/test_replay_bundle_contract.py -q`.
The fixture is local synthetic evidence, not a provider run. Tests cover exact
round-trip preservation, network prohibition, resealed internal inconsistencies,
unknown schema, truncation/error states, missing observations, duplicate JSON,
credential fields and the input size limit.

Next R2 increment: capture actual request inputs and complete responses at the
executor boundary, with trustworthy oracle identity and explicit origin links,
then export through the CLI. Only then close R2 and proceed to R3 replay. Do not
change historical artifacts or invoke remote generation merely to validate one.

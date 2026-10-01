# R2 — replay evidence storage contract

Status: initial Python storage/validation contract and opt-in executor transport
capture implemented; their integration and CLI export are pending. R2 is not
closed. R3 oracle execution and repair
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

Next R2 increment: bind captured exchanges to task/variant/oracle identity with
explicit source links and an explicit prompt-transformation contract, then export
through the CLI. Only then close R2 and proceed to R3 replay. Do not
change historical artifacts or invoke remote generation merely to validate one.

## Executor transport capture

`NebiusExecutor.capture_exchange(system_prompt, user_prompt)` makes **one new
provider request**, or records BLOCKED when credentials are absent. It is an
alternative to `execute`, not an accessor for a previous execution. No automatic
capture is added to existing behavioral/confirmation/repair callers.

The returned `crucible-executor-capture/v1` envelope is transport evidence only:

- `guidance` retains the caller's original system/user strings.
- `request.body` is the exact UTF-8 JSON body supplied to the transport, with
  `body_digest`. It uses the same request builder as legacy execution, including
  the empty-guidance fallback `You are a helpful assistant.`.
- `attempted` means the opener was invoked, not that the server received it.
- `response` is null if unavailable; otherwise it records HTTP status, exact
  body bytes encoded as base64, their digest, and transport `complete` (EOF).
- `status` distinguishes BLOCKED, RECEIVED, HTTP_ERROR, TRANSPORT_ERROR and
  RESPONSE_LIMIT. RECEIVED does not claim valid JSON, model completion or acceptance.
- `error` contains only controlled labels, not exception messages. The outer
  `capture_digest` seals all fields except itself using canonical JSON/SHA-256.

Request bodies are limited to 1,000,000 bytes before network execution. Response
reads use chunks of at most 65,536 bytes and admit at most 4,000,000 bytes, with
one extra sentinel byte to detect overflow. On overflow the retained body is a
prefix, explicitly incomplete; its digest covers only that prefix. Read failures
retain already-observed bytes and `IncompleteRead.partial` where available.
No retries occur. The 60-second transport timeout is not a total capture deadline.

Authorization/other headers, endpoint URLs and exception messages are not exported.
Bodies remain private: prompts or a provider error can themselves contain secrets.
No content redaction is claimed. Provider identity is a configured label, not
proof of endpoint authenticity; redirects/TLS metadata are not captured. The seal
does not prevent a malicious author from replacing and resealing the capture.

This envelope is deliberately **not accepted** by `validate_bundle`. The replay
v1 exact-guidance invariant cannot represent the baseline prompt fallback.
Silently changing either historical behavior or captured guidance would falsify
provenance. The next integration must version that transformation explicitly,
pin the oracle and link observations to the captured response. Raw bytes also
avoid legacy execution's zero-filled missing usage metadata; capture invents none.

Run `PYTHONPATH=src python3 -m pytest tests/test_runtime_capture.py -q`.
All transport tests replace the HTTP opener; they are not real provider evidence.

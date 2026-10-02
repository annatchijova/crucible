# R2 — replay evidence storage contract

Status: v1 storage validation and v2 capture-backed acquisition are implemented.
Optional local journaling retains committed partial work. CLI acquisition,
inspection and export are locally verified for the current four-way adapter,
closing R2's bounded storage/acquisition/export gate. No new live-provider run
is claimed. R3 offline replay is locally verified for the retained property
observations. The code review and its negative-control evidence are recorded in
the repository's red-team review log. Provider authenticity and L7 repair
acceptance replay remain outside R3.

`src/crucible/replay.py` exposes `validate_bundle`, `dump_bundle`, `load_bundle`
and `replay_readiness`. All are offline and side-effect-free. JSON is limited
to 8,000,000 UTF-8 bytes, 500 variants and 100 task properties. Unknown versions,
unknown fields, duplicate JSON keys and nonfinite JSON constants are rejected.

## Versioned envelope v1

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

Inspection and export below do not perform replay. Do not change historical
artifacts or invoke remote generation merely to validate one.

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

This standalone envelope is deliberately **not accepted** as a bundle by
`validate_bundle`. The replay
v1 exact-guidance invariant cannot represent the baseline prompt fallback.
Silently changing either historical behavior or captured guidance would falsify
provenance. The v2 integration below versions that transformation explicitly,
pins the oracle and links observations to the captured response. Raw bytes also
avoid legacy execution's zero-filled missing usage metadata; capture invents none.

Run `PYTHONPATH=src python3 -m pytest tests/test_runtime_capture.py -q`.
All transport tests replace the HTTP opener; they are not real provider evidence.

## Capture-backed bundle v2

`crucible-replay-bundle/v2` retains the v1 task, variant and oracle fields and adds
`request_adapter: nebius-chat-guidance/v1`. Each run has exactly `variant_id`,
`capture` and `observations`. The embedded capture's seal links its request and
response bytes; the outer seal links that evidence to the task, variant and
observations. Derived request/response projections are not duplicated in storage.

The adapter permits only the existing two-message, non-streaming request shape,
integer sampling controls, and the documented empty-system-guidance fallback.
Original guidance must match the variant's exact text; user guidance must match
the full task prompt. Captured wire messages must match that declared adapter.
Unknown request fields, adapters or versions are rejected, not normalized away.

`capture_contract.validate_capture` checks strict fields, status/attempt/HTTP
consistency, canonical base64, byte limits, body digests and the capture seal.
`capture_projection` derives response text and metadata without touching a provider.
Duplicate JSON keys, nonfinite constants, malformed UTF-8/JSON, invalid choices,
non-text output and invalid usage counts do not produce usable observations.
Raw response bytes remain preserved even when projection fails. Missing or partial
usage stays unknown rather than becoming zero. Unknown provider fields remain in
raw evidence; they cannot specify the local oracle or change the request contract.

`capture_bundle.capture_behavioral_bundle(executor, task=None, variants=None, journal=None)`
acquires a **new experiment**. Inputs are copied before execution. Defaults are
the current four-way behavioral fixtures, not an importer for historical runs.
It calls `capture_exchange` once per variant, computes observations from the
captured textual output with the local lexical oracle, and validates the result.
Blocked/error runs are retained without a local fallback. Truncated textual output
may carry historical observations but never earns complete-evidence readiness.

The oracle ID is `crucible-lexical-properties/v1`. Its implementation digest covers
the source text of the oracle, checks and helpers, the dispatch mapping, and
`sys.version`. Identity is checked before and after acquisition. This conservatively
invalidates identity after source/runtime changes. Local code and source files are
trusted; this is not runtime-code attestation or a signature. R3 must match a trusted
installed oracle and recompute observations before any acceptance decision.

`validate_bundle`, `dump_bundle`, `load_bundle` and `replay_readiness` support both
versions. They do not execute the oracle, import code from artifacts or call a
provider. v1 seals/fields are retained exactly; no v1→v2 migration is offered,
because v1 does not retain capture bytes. Unknown versions fail visibly.

The 8 MB bundle limit includes base64 expansion and all embedded captures. Input
size is checked before acquisition; accumulated size is checked after each run,
before another provider call. On an aggregate-limit stop or detected oracle drift,
`CaptureAssemblyError.partial_evidence` retains the collected experiment in memory
without a bundle version/seal. It is not a valid replay bundle. Without an explicit
journal, this remains in-memory storage: process crashes and other acquisition
exceptions can lose evidence. The optional journal below checkpoints partial work;
the CLI below exposes acquisition, inspection and export of stored complete bundles.

Run `PYTHONPATH=src python3 -m pytest tests/test_capture_bundle.py tests/test_replay_bundle_contract.py -q`.
Transport is mocked in these tests; no live provider evidence is claimed.

## Incremental local journal

`CaptureJournal(new_directory)` creates a private POSIX directory (0700) and
`evidence.sqlite3` (0600). Existing destinations, including symlinks, are never
reused or overwritten. Parent directories and SQLite files must be trusted local
storage; this is not a sandbox or an importer for hostile SQLite databases.

Pass it explicitly as the keyword-only `journal` argument to
`capture_behavioral_bundle`. The lifecycle is:

1. Commit the frozen experiment metadata before any provider call.
2. Commit each returned, validated raw capture before projection/oracle execution.
3. Commit observations separately; null means they were not recorded, not that
   an empty observation list was produced.
4. After validation, commit the complete bundle only if it matches every saved
   capture, observation and input. No artifact content is rewritten during recovery.

Transactions use `BEGIN IMMEDIATE`, a five-second busy timeout, WAL and
`synchronous=FULL`. This adapts the atomic-state-mutation transaction pattern with
the stronger synchronization setting for retained evidence. Schema initialization
is transactional; directory entries are synchronized at initialization. Payload
storage is bounded to 500 captures and 24,000,000 combined JSON bytes, including
the final bundle. This is not a bound on total SQLite/WAL filesystem allocation.
Failed writes roll back and abort acquisition before the next provider call.

`read_journal(directory)` opens SQLite read-only and reads one consistent snapshot,
checks stored digests/capture links, and validates any completed bundle. It returns
`crucible-capture-journal/v1`, status EMPTY/PARTIAL/COMPLETE, metadata, captures,
pending variants and variants whose observations were not recorded. SQLite
`user_version=1` identifies the persistent schema; unknown versions are rejected.
The reader calls neither provider nor oracle. SQLite may manage WAL/shared-memory
sidecars; preserve the directory, not just the main database file, while active.

COMPLETE means acquisition and bundle storage finished, **not** evidence readiness
or acceptance: a bundle whose responses are all BLOCKED can be stored completely.
There is no automatic replay, retry or resume. A missing capture does not prove
the provider was never contacted; do not reissue requests based on that inference.

Committed records survive the tested abrupt process exit and transaction failures.
This does not promise recovery of a response lost before its capture commit, an
in-flight response, hardware/filesystem failure, or malicious deletion/resealing.
Durability relies on the filesystem honoring SQLite synchronization. Disk-full or
validation failure can prevent the current capture from being committed; earlier
commits remain the recovery boundary. An incomplete initialization fails visibly
rather than fabricating an empty valid experiment. Failed directories are retained
for inspection and not cleaned up automatically.

Run `PYTHONPATH=src python3 -m pytest tests/test_capture_journal.py -q`.
Tests include a subprocess exiting with `os._exit` without closing SQLite, injected
write/commit-path failures, refusal to overwrite/reuse, and read-after-interruption.
Provider calls are blocked or mocked; no real-provider durability run is claimed.

## Journal CLI

These modes are mutually exclusive and cannot be combined with a corpus path or
other CLI options. Existing modes retain their previous behavior. The acquisition
mode uses the built-in four-way task and Nebius adapter; it does not support custom
tasks or `--local-executor`. Missing credentials produce retained BLOCKED evidence,
not a simulated successful provider run.

| Command | Authority and output |
|---|---|
| `--capture-replay NEW_DIRECTORY` | May issue four provider requests; creates an exclusive private journal; prints summary only |
| `--inspect-replay JOURNAL_DIRECTORY` | Offline; prints status/counts and pending/unobserved/incomplete variant IDs, not bodies |
| `--export-replay JOURNAL_DIRECTORY` | Offline; validates and prints the stored complete bundle, including private bodies, to stdout |

The summary is versioned `crucible-replay-cli/v1`. `status` is persistence status,
`evidence_complete` is the existing readiness check, not oracle correctness or an
acceptance verdict. `incomplete_variants: null` means no complete bundle exists;
use `pending_variants` and `unobserved_variants` to inspect that partial state.

| Exit code | Meaning |
|---|---|
| 0 | Stored complete bundle with complete evidence metadata; **not acceptance** |
| 1 | Valid journal/evidence is incomplete, blocked, truncated, empty or partial |
| 2 | Usage error, invalid/unreadable journal, conflicting options or operational failure |
| 130 | Interrupted command; inspect any retained journal before deciding what to do |

Export emits valid complete bundles even when evidence is incomplete (exit 1),
so failed/blocked outcomes remain archivable. It emits no JSON for EMPTY/PARTIAL
journals (exit 1) or invalid journals (exit 2); it never manufactures missing runs.
Retain the original private journal directory for partial evidence. An export
interrupted while writing stdout may leave a partial destination file: verify it
with `load_bundle`, or export again from the unchanged journal. Export is not an
atomic destination-file replacement operation.

Example (choose a trusted existing parent outside the repository; do not publish
private evidence). Acquisition can incur provider usage; the other two commands
never contact the provider even if credentials are configured:

```bash
PYTHONPATH=src python3 -m crucible.cli --capture-replay /trusted/evidence/new-experiment
PYTHONPATH=src python3 -m crucible.cli --inspect-replay /trusted/evidence/new-experiment
# Protect a new export file from broad permissions and accidental overwrite:
umask 077
set -o noclobber
PYTHONPATH=src python3 -m crucible.cli --export-replay /trusted/evidence/new-experiment > replay-bundle.json
```

Do not put keys on the command line. Existing `NEBIUS_API_KEY` configuration is
used only for acquisition. Diagnostics suppress arbitrary exception text because
it may contain private data. A failed capture command leaves committed records
for inspection; it does not automatically resume or retry a provider request.
SQLite recovery constraints and pre-commit loss windows remain as documented above.

Reproduce the local CLI boundary checks with
`PYTHONPATH=src python3 -m pytest tests/test_replay_cli.py -q`.

## R3 — offline oracle replay

`--replay-bundle BUNDLE_JSON` runs the local property oracle only when the
bundle's recorded oracle ID and implementation digest exactly match the
installed trusted oracle. It requires complete evidence, recomputes every
property status from the retained response text, and compares the result with
the stored observation. The versioned `crucible-oracle-replay/v1` result records
the source bundle digest, both oracle identities, and per-property agreement;
its own digest seals that replay result. Exit 0 means statuses matched, exit 1
means the evidence cannot be replayed or statuses diverged, and exit 2 means
the input could not be loaded or validated.

`--reevaluate-bundle BUNDLE_JSON` is an explicit new evaluation using the
currently installed oracle, including when its identity differs from the
historical oracle. Its result says `REEVALUATED_MATCH` or
`REEVALUATED_DIVERGED`, retains the historical oracle identity, and never
rewrites the bundle or its recorded observations. Both actions are offline:
they do not construct a provider executor or make network requests.

The replay outcome means only that per-property statuses match under the named
local oracle. It does not authenticate the provider, prove a response came from
the named model, assess skill quality, or re-run L7 repair acceptance. A valid
digest and a matching replay can be produced from a maliciously authored and
resealed bundle; source authenticity remains outside this contract. Oracle
identity also trusts the installed Python source/runtime and is not runtime code
attestation. Incomplete bundles, including blocked or truncated runs, are never
passed to the oracle.

R3's local negative controls cover exact-oracle mismatch, resealed observation
tampering, incomplete response refusal, explicit re-evaluation, v1 replay and
offline CLI behavior. The observation-tampering test was mutation-checked: making
both sides of the comparison use the recorded status caused the test to fail.
See the [R3 code review and evidence](red-team/2026-10-01-r3-replay-code-review.md).

Run the focused R3 and inherited replay contracts with:

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_oracle_replay.py tests/test_replay_bundle_contract.py tests/test_capture_bundle.py tests/test_replay_cli.py
```

# L7 repair evidence bundle

`crucible --repair-loop --llm-proposer --repair-evidence NEW_PRIVATE_DIR`
captures one real Nebius-backed repair run. The destination must not already
exist. On POSIX, the directory is created `0700`, evidence files `0600`, and
each raw request/response exchange is appended and fsynced before projection
into the L7 workflow. The command prints only the path, outcome, event count,
and bundle digest; prompts and provider outputs stay on disk.

The `crucible-repair-evidence/v1` bundle binds the original corpus and its text
digests, task and digest, finding index, base audit digest, loop and property
oracle identity, request/response captures, response IDs, finish reasons,
usage (including explicit absence), errors, and the L7 report. The proposal
request uses the existing LLM proposer configuration; the two behavioral
requests use the existing Nebius executor configuration. Events are ordered and
linked with payload digests. The outer bundle digest seals their collected
representation. `verify_repair_evidence` checks internal bundle/source/event
consistency offline; it does not authenticate Nebius or anchor the digest
outside the local evidence directory.

`crucible --replay-repair-evidence BUNDLE_JSON` reconstructs the L7 decision
offline from recorded response projections. It requires the current repair-loop
and property-oracle identities and checks that captured prompts and request
configuration match the local repair inputs. It feeds those recorded outputs
through the existing compile, audit, behavioral-oracle, and acceptance path; it
never creates a provider executor or makes a network call. `MATCH` means the
decision surface reproduces, `DIVERGED` means it does not, `NOT_REPLAYABLE` means
the current implementation or event sequence cannot replay that bundle, and
`INVALID_EVIDENCE` means local structure/seal validation failed. The command
exits zero only for `MATCH` and prints a summary without captured prompts or
outputs. Decision comparison omits only executor class labels, so raw loop
digests can differ while decision digests match. This remains local
recomputation, not provider authentication or an external timestamp/signature.
The CLI rejects duplicate JSON keys and non-finite constants and enforces the
bundle byte limit while reading the file. See the [L7 replay parser red-team
review](red-team/2026-10-07-l7-repair-replay.md) for the reproduced negative
control and its scope.

Incomplete, malformed, errored, or truncated provider responses are retained.
They are not eligible to produce a proposal or behavioral observation. Loop v2
also applies this gate in the ordinary repair loop: a Nebius response must have
`finish_reason=stop`, `truncated=false`, a nonempty response ID and output, and
consistent token usage before its observations can support `ACCEPTED`. A
length-limited or metadata-incomplete LLM proposal is not passed to re-audit.
Captured runs retain every attempted exchange; ordinary runs return
`ERROR / INCOMPLETE_PROVIDER_RESPONSE` without claiming the response was
captured. Rejected, blocked, and error reports remain evidence outcomes, not
successful repairs. Historical v1 loop reports are unchanged.

Captures can contain the full skill text, task, and provider response. Keep the
directory private and apply the provider's data-handling rules. Do not commit
generated repair evidence. A crash before an HTTP response is returned may
leave an attempted request without a response body; there are no automatic
retries or recovery claims. These records prove what this process retained,
not server receipt, model identity, or unchanged remote execution. One favorable
run is not a stability benchmark or independent evaluation.

## 2026-10-02 captured run

The private fixture capture at
`/tmp/crucible-r4-20261002-structure-v1` is a complete, verifiable failed
outcome. Its single proposal response has `finish_reason=length`; the L7 loop
returned `REJECTED / NO_PROPOSAL` before deterministic re-audit or behavioral
replay. The bundle digest is
`sha256:64fd5016e72121eada892bfa1656786e85446feae44fc4e7677e7c63dc8d9a6e`.
The offline verifier and raw-capture-to-event comparison both pass. The repair
proposal token cap is now 3,000 (previously 1,000) in both captured and regular
Nebius proposer paths. At that point, a bounded follow-up capture was needed
before R4 could advance; its result is recorded below.

The bounded follow-up capture at
`/tmp/crucible-r4-20261002-structure-v2` completed with `ACCEPTED`. Its bundle
digest is
`sha256:38158eeeced17a01bc7f0b28ea04d8d27d166ab7f2c242b354ee14105929c19d`.
The original audit had two findings and the repaired audit had zero; the
original finding was gone, no new finding appeared, and the behavioral replay
changed the seeded P3 property from FAIL to PASS while the other three
properties remained PASS. All three provider events were complete with
`finish_reason=stop`; offline bundle verification and raw-capture comparisons
pass. This is a single synthetic fixture demonstration, not an estimate of
repair accuracy or stability.

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

Incomplete, malformed, errored, or truncated provider responses are retained.
They are not eligible to produce a proposal or behavioral observation, and an
otherwise `ACCEPTED` L7 report is downgraded to `ERROR` if any captured response
lacks complete response status, finish reason, usage, or non-truncation. The
existing L7 deterministic/behavioral policy is otherwise unchanged. Rejected,
blocked, and error reports remain evidence outcomes, not successful repairs.

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

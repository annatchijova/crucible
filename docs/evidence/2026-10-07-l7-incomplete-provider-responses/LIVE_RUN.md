# L7 live run after incomplete-response fix

**Date:** 2026-10-07  
**Branch / code:** `work/independent-evaluation-20261007` at `87bb4a9`  
**Provider:** Nebius Token Factory (`nvidia/nemotron-3-super-120b-a12b`)  
**Fixture:** built-in synthetic `LOOP_FIXTURE` and `TASK_FIXTURE`

## Result

The captured proposal request received HTTP 200. Its response had
`finish_reason=stop`, a response ID, nonempty output, and consistent usage
metadata (456 prompt, 1,108 completion, 1,564 total tokens). The LLM proposal
was therefore eligible for deterministic re-audit.

The loop returned `REJECTED / NEW_FINDINGS`: the fixture began with two
findings (`METHODOLOGICAL_VACUITY`, `REQUIREMENT_WITHOUT_CHECK`); after the
proposal, the targeted finding was gone, but the audit found five
`COMMAND_ORACLE_WITHOUT_ARTIFACT` findings. The deterministic gate rejected the
proposal before behavioral replay. This is a valid rejection, not a successful
repair, and it does not exercise the behavioral-response guard added in loop
v2.

The private bundle is at
`/tmp/crucible-l7-live-20261007-02/bundle.json`; its digest is
`sha256:25dd3ee9e67a2decff33913e5cd02af077621780e1ca3f2a4a22ee54a356e52e`.
`verify_repair_evidence` returned true. The capture directory is mode `0700`
and its files are mode `0600`. The bundle contains the fixture text, prompts,
and raw provider output, so it remains outside the repository and must not be
published or committed.

An earlier attempt inside the restricted shell recorded a single
`TRANSPORT_ERROR` without an HTTP response. It is preserved separately at
`/tmp/crucible-l7-live-20261007-01` and is not counted as a provider response.

## Red-team reading

- The provider response passed the completeness checks at the proposal
  boundary; this is direct live evidence for that edge of the updated flow.
- The deterministic re-audit caught unsupported command-oracle findings and
  prevented acceptance. No behavioral calls were made after that rejection.
- The run demonstrates one request and one fixture outcome only. It says
  nothing about repair success rates, repeatability, or behavioral replay
  against Nebius.
- The recorded digest detects changes only relative to this local bundle; it
  is not a provider signature or an externally anchored proof.

## Prompt follow-up

Inspection of the captured proposal showed five checks starting with
verification verbs (`Verify`, `Check`, `Assert`, `Confirm`, `Demonstrate`). The
repair guidance itself asked for those verbs. The compiler classifies them as
command oracles, and the auditor requires a named artifact for that class; the
proposal named none. The rejection was correct, while the prompt guidance was
misaligned with the auditor's contract.

The LLM guidance for both `METHODOLOGICAL_VACUITY` and
`REQUIREMENT_WITHOUT_CHECK` now asks for at most three observable behavioral
questions ending in `?`, and forbids inventing script paths or unsupported
commands. The deterministic proposer also stopped emitting the nonexistent
`scripts/check_requirement.sh` path and now uses bounded behavioral questions.
Regression coverage checks both prompt classes and reproduces the five-check
rejection shape, including the guarantee that L7 stops before behavioral
replay. The deterministic proposer no longer emits a nonexistent script path.
The full local pytest suite passes.

This local fix did not by itself prove that Nemotron follows the revised
guidance. The follow-up captured run below provides one such check. Keep raw
captures private.

## Follow-up captured L7 run

**Code:** branch `work/independent-evaluation-20261007` at `7ad3e71`

**Result:** `ACCEPTED` on the built-in synthetic fixture

The proposal and both behavioral requests received HTTP 200. All three
responses had `finish_reason=stop`, response IDs, nonempty output, and
consistent token usage:

| Stage | Prompt tokens | Completion tokens | Total |
|---|---:|---:|---:|
| Repair proposal | 490 | 1,091 | 1,581 |
| Original behavior | 100 | 2,314 | 2,414 |
| Repaired behavior | 239 | 1,908 | 2,147 |

The deterministic audit changed from two findings
(`METHODOLOGICAL_VACUITY`, `REQUIREMENT_WITHOUT_CHECK`) to zero, with no new
findings. Behavioral replay was complete with no regression: P1, P2, and P4
passed before and after; P3 changed from `FAIL` before repair to `PASS` after
repair. The loop returned `ACCEPTED`.

The verified private bundle is at
`/tmp/crucible-l7-live-20261007-04/bundle.json`; its digest is
`sha256:8ec4ca662cc09d743144d3117906d8876bebf91dc33b138e9626ee2093620e2c`.
Its directory is mode `0700` and files are `0600`. It contains raw prompts and
provider output and remains outside the repository.

One sandboxed retry at `/tmp/crucible-l7-live-20261007-03` ended in
`TRANSPORT_ERROR` before HTTP. It did not count as a provider response; the
successful capture used a fresh directory outside the restricted shell.

### Red-team bounds

- This is direct live evidence that the revised repair guidance passed the
  deterministic gate and exercised both behavioral calls once.
- Acceptance is for this synthetic fixture and this one model run. It is not a
  repair success-rate estimate, repeatability result, or validation against
  external skill repositories.
- The behavioral oracle checks the fixture's declared properties; it is not an
  independent semantic assessment of the generated repair.
- Bundle verification checks the local seal and event chain, not provider
  identity or an externally anchored digest.

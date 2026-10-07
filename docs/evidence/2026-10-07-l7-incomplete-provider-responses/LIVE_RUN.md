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

## Next engineering step

Review why the proposal introduced five command oracles without artifacts,
then improve the proposer prompt or fixture guidance and add a regression
case. After that, repeat the captured run and require a proposal to pass the
deterministic gate before using another live call to exercise both behavioral
requests. Keep raw captures private.

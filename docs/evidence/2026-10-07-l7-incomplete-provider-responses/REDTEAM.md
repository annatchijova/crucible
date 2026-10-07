# L7 rejects incomplete Nebius responses

Date: 2026-10-07

## Claim under review

An incomplete provider completion cannot contribute to a successful L7 repair, even when its text is plausible and passes the deterministic audit or lexical property checks.

## Attack and failure case

Two negative controls were run before remediation. First, `LLMProposer` received a plausible repaired `SKILL.md` with `finish_reason=length` and returned it as a proposal. Second, a Nebius-labeled executor returned property-passing text with `truncated=true`; `run_repair_loop()` returned `ACCEPTED`. Both tests went red against the prior implementation.

## Remediation

The LLM proposer now refuses proposal text unless `finish_reason=stop`; truncated or finish-metadata-missing text is not re-audited. The Nebius behavioral adapter marks runtime metadata complete only when the response has a nonempty ID/output, stop completion, and complete consistent nonnegative integer token counts. The L7 loop independently checks that metadata and returns `ERROR / INCOMPLETE_PROVIDER_RESPONSE` without running the property oracle when either behavioral response is incomplete. The captured executor propagates its checked-complete state. The repair-loop artifact version advanced to `crucible-repair-loop/v2`; historical v1 reports remain unchanged.

## Verification

- Length-limited proposal text rejected: passed.
- Truncated behavioral response rejected even when a test executor claims complete metadata: passed.
- Missing usage and fully complete provider metadata controls: passed.
- Captured-repair completeness contracts and end-to-end local loop tests: passed.
- Full test suite and `git diff --check`: passed.

## Limits

This is local contract evidence, not a new live-provider run. The current shell environment has no `NEBIUS_API_KEY`. Ordinary L7 responses are checked before acceptance but are not raw-captured; use `--repair-evidence` for retained request/response evidence. One live repair after this version change is still needed before claiming current end-to-end Nebius verification.

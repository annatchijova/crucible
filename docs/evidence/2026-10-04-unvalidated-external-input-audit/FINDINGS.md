# UNVALIDATED_EXTERNAL_INPUT audit: polarity fixed, an "environment variable" scope question deferred

**Date:** 2026-10-04
**Context:** continuation of the systematic L2-check held-out audit.
5 hits on terminalskills.

## Read all 5 in full. Two mechanisms

### Mechanism A: polarity blindness (2/5) — 4th instance this session

- `pytorch` rule-0001 (modality `NEVER`): "Never `torch.load` a
  checkpoint from an untrusted source with `weights_only=False`; it can
  execute arbitrary code." The rule prohibits the unsafe pattern; it
  doesn't instruct it.
- `great-expectations` rule-0001 (modality `NEVER`): "Never put a
  database password directly in a connection string in code; read it
  from an environment variable." Same shape -- a prohibition whose
  recommended-alternative clause ("read it from an environment
  variable") happens to match `_EXTERNAL_INPUT_PATTERNS`.

Same `_NEGATIVE_MODALITIES` guard already reused for NON_DETERMINISTIC_
INSTRUCTION, IRREVERSIBLE_WITHOUT_REVIEW, and UNBOUNDED_RETRY this
session.

### Mechanism B: "environment variable" is operator-controlled configuration, not attacker-controlled input — deferred, not fixed

- `sentry` step-0002: "Read the DSN from an environment variable."
- `val-town` step-0001: "Read secrets with `Deno.env.get(\"NAME\")`...;
  set them in the val's settings."
- `urql` step-0008: "read tokens **at request time**... never hardcode
  them" -- a different flavor of the same root issue: "request" here
  means "at the moment the app makes its own outbound HTTP request,"
  not "an inbound HTTP request being parsed" -- a word-collision false
  positive layered on top of the same `environment_variable`/secret-
  management pattern.

`environment_variable` is one of the terms in `_EXTERNAL_INPUT_PATTERNS`
alongside `user_input`/`request`/`stdin`/`argv`/`query_parameter`/
`uploaded_file` -- all genuinely attacker-reachable in the usual threat
model. An environment variable is typically operator/deployer-set
configuration (a secret, a DSN, a feature flag), not something an
external attacker controls the same way. In all 3 remaining hits, the
instruction is literally the *recommended secure practice* for secret
management (read the credential from env, don't hardcode it) --
structurally the same virtue `HARDCODED_CREDENTIAL` rewards, miscast
here as a risk.

Not fixed: removing `environment_variable` from the pattern list
outright risks losing a genuine case where an env var IS attacker-
influenced (e.g. a CLI tool that blindly trusts `$PATH`/`LD_PRELOAD`, or
a web framework that reads a request-controlled header into an env-like
config object) -- the same caution already applied to CHECK_WITHOUT_
ORACLE's deferred mechanism C and REQUIREMENT_WITHOUT_CHECK's mechanism
B: a vocabulary change here is a scope decision, not a mechanical fix.

## Verified by diffing skill+rule-id sets

| Corpus | Before | After | Removed | Added |
|---|---|---|---|---|
| microsoft-skills | 0 | 0 | 0 | 0 |
| sports-skills | 0 | 0 | 0 | 0 |
| terminalskills | 5 | 3 | 2 | 0 |
| mukul975 | 2 | 2 | 0 | 0 |
| Author's own corpus | 1 | 1 | 0 | 0 |

2 new regression tests (positive/negative modality pair). Full suite
and mutation gate green.

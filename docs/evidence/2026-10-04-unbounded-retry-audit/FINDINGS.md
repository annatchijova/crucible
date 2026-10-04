# UNBOUNDED_RETRY audit: two narrow fixes, several deferred descriptive-vs-prescriptive cases

**Date:** 2026-10-04
**Context:** continuation of the systematic L2-check held-out audit.
11 hits on the held-out corpora (microsoft-skills 1, sports-skills 1,
terminalskills 9... re-measured as 10 total at audit time).

## Read all 11 in full. Two clean, narrow mechanisms, plus a mixed bag of harder ones

### Mechanism A: polarity blindness (1 hit) — 3rd instance of this bug shape this session

`sports-skills/polymarket-trading` rule-0005, modality `MUST_NOT`: "Do
not retry failed orders in a loop." The check never consulted the
rule's own modality, so a rule that *forbids* unbounded retry was
flagged as instructing one. Same shape already fixed for
NON_DETERMINISTIC_INSTRUCTION (this session) and IRREVERSIBLE_WITHOUT_
REVIEW (the parallel session).

### Mechanism B: bound-vocabulary word-form gaps (2 hits)

- `terminalskills/agent-swarm-orchestration`: "Set retry **limits**
  (typically 3)..." — `\blimit\b` didn't match the plural "limits".
- `terminalskills/runway-ml`: "...**backing off**; the SDKs retry some
  errors **twice** by default." — `\bbackoff\b` didn't match the gerund
  "backing off" (two words), and no pattern accepted a written-out
  count ("twice") alongside a digit count.

## What was fixed, on Anna's go-ahead

- `_check_unbounded_retry`'s rules loop now skips a rule whose modality
  is in `_NEGATIVE_MODALITIES` (reused as-is, same constant as the
  other two fixes).
- `_RETRY_BOUND_PATTERNS`: `\blimit\b` -> `\blimits?\b`; `\bbackoff\b`
  -> `\bback(?:ing)?\s*off\b` (still matches the original compound noun,
  now also the gerund); added `\b(?:once|twice|thrice)\b`.

5 new regression tests (positive/negative pairs for each). Verified by
diffing skill+rule-id sets across every corpus available, not just
counting:

| Corpus | Before | After | Removed | Added |
|---|---|---|---|---|
| microsoft-skills | 1 | 1 | 0 | 0 |
| sports-skills | 1 | 0 | 1 | 0 |
| terminalskills | 10 | 7 | 3 | 0 |
| mukul975 | 4 | 3 | 1 | 0 |
| Author's own corpus | 6 | 6 | 0 | 0 |

mukul975 lost one case too (the same vocabulary gap generalizes beyond
the held-out corpus, a good sign). Zero new findings anywhere. Full
suite and mutation gate green.

## Deferred: the remaining mix is descriptive-vs-prescriptive, same family as NON_DETERMINISTIC_INSTRUCTION's open mechanisms

Read the rest in full:

- `azure-eventgrid-py`: "**Handle retries** — Event Grid has built-in
  retry" — describes a platform capability, not an instruction.
- `apollo-client`: "**Error link** — Use `onError` link... (auth
  refresh, logging, retry)" — "retry" is one item in a feature list.
- `cors`: "...reduces **repeat** `OPTIONS` requests" — "repeat" here
  means repeated browser preflight requests, unrelated to a retry loop
  at all -- a pure word-collision false positive, same class as
  NON_DETERMINISTIC_INSTRUCTION's "Random Forest" case.
- `systems-thinking`: "**REPEAT** — Once this constraint is broken,
  find the NEW constraint" — a named step in a Theory-of-Constraints
  methodology, not a retry-loop instruction.
- `urql` (2 hits): "Auth, Retry and Subscriptions" (a section-title-like
  fragment) and an architecture description listing "retry" as one kind
  of exchange — neither is an instruction to retry anything.
- `trigger-dev`, `webhook-processor`, `function-calling`: genuinely
  vague ("Set appropriate retry strategies...", "Implement the worker
  with retry logic", "Repeat until the model returns a final text
  response") -- plausible true positives, no bound stated anywhere.

Not fixed. These require the same prescriptive-vs-descriptive text
signal flagged as an open design question for NON_DETERMINISTIC_
INSTRUCTION's mechanisms 1-6 -- not a vocabulary-list patch.

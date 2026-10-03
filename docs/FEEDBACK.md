# Feedback on tools and models

**Date:** 2026-10-03
**Scope:** operational notes from running this project against the real
Nebius Token Factory API with `nvidia/nemotron-3-super-120b-a12b`, across
every session that touched a live provider call (2026-09-30 through
2026-10-03). This is the hackathon's requested "feedback on tools/models"
deliverable (`docs/NVIDIA_INTEGRATION.md`'s requirement-to-evidence
matrix listed this row as `PLANNED`; it is now `DONE`, this document).

Every claim below points to a specific run, artifact, or commit. Where a
finding generalizes beyond the one run that surfaced it, that is stated;
where it does not, that is stated too. "One favorable run is not a
stability benchmark" applies throughout — see
`docs/REPAIR_EVIDENCE.md`.

## Nemotron in practice

### Latency

Consolidation proposals (`LLMConsolidationProposer`, a few hundred
input tokens of skill text, JSON-object output): **~5 seconds per call**
observed across 5 live calls (4.9s, 5.4s, 4.8s, and two calls totaling
7.0s in a batch) — see `docs/L16_NEBIUS_LIVE_RUN_EVIDENCE.md`. Behavioral
differential calls (shorter completions, retry-strategy-design task):
completed without truncation at a 4000-token budget after an earlier
500/2000-token budget produced intermittent truncation (see "Truncation"
below). No call in any session timed out against this project's 60-90
second client-side timeout.

### Truncation and empty content — the two failure modes that actually occurred

Both came from the 2026-09-30 red-team round
(`docs/red-team/2026-09-30-nebius-runtime-red-team.md`, NR-01/NR-02), not
from speculation:

- **`content: null`.** Two of four real behavioral-differential variants
  returned a JSON response with `choices[0].message.content: null` — a
  structurally valid response with no text. The first real run crashed
  on it (`AttributeError: 'NoneType' object has no attribute 'lower'` in
  the property oracle; the equivalent `.strip()` call in the Bob proposer
  path had the same latent bug). This is now handled by validating
  `choices`/`message`/`content` at every provider boundary and returning
  an explicit error with `finish_reason`, truncation state, and usage
  instead of letting untyped data reach deterministic logic — but the
  lesson is the one worth keeping: **a 200 response with null content is
  a real, observed shape from this model**, not a hypothetical edge case
  defensive code happens to cover.
- **Truncation at low token budgets.** Controlled calls at 500 and 2000
  tokens for the behavioral task both ended with `finish_reason=length`.
  A 4000-token budget completed all four variants with `finish_reason=stop`.
  Separately, the L7 repair-proposal budget hit the same wall at
  1000 tokens (`docs/REPAIR_EVIDENCE.md`'s 2026-10-02 captured run,
  `finish_reason=length`, `REJECTED/NO_PROPOSAL`); raising it to 3000
  produced a complete, `ACCEPTED` proposal on the next attempt. **This is
  a reasoning model that spends tokens on deliberation before the
  requested output** — a token budget sized for the expected output
  length alone was consistently insufficient across two independent
  task types (behavioral completion, repair/merge proposal). Every
  executor and proposer in this project now records `finish_reason` and
  a `truncated` boolean in its response envelope specifically because of
  this.

### Instruction-following quality

- **Passive context is not causal.** The single highest-severity finding
  (NR-03, red-team 2026-09-30): when a mutated (unsafe) methodology was
  supplied only as background context, Nemotron ignored it and
  substituted its own default safe advice — the behavioral differential
  showed no difference between the mutant and the original, which would
  have falsely suggested the mutation had no effect. Only after adding an
  explicit instruction ("apply the supplied methodology exactly") did the
  mutant produce the unsafe recommendation the experiment was designed to
  detect. **A skill or methodology handed to this model as passive
  context will often not be followed; it has to be imperatively
  activated.** This shaped every subsequent prompt in this project
  (`REPAIR_SYSTEM_PROMPT`, `CONSOLIDATION_SYSTEM_PROMPT`) to explicitly
  instruct rather than merely inform.
- **Structured-output compliance was reliable.** `LLMConsolidationProposer`
  asks for a JSON object with exactly two keys (`name`, `text`) and no
  other text. Across all 5 live L16 calls (2026-10-03), the model
  returned parseable JSON with no preamble, fences, or extra keys, and
  no `json.JSONDecodeError`. This is a narrower, more recent sample than
  the other findings here (one session, one prompt shape) — it says this
  particular structured-output pattern worked every time it was tried,
  not that the model's JSON compliance is unconditionally reliable.
- **Content quality on consolidation merges was good within the sample
  tried.** Across 4 real merge proposals, Nemotron never dropped a rule
  or check that a stricter prompt review would flag as missing — including
  a case specifically constructed so each input skill had one check the
  other did not (`docs/L16_NEBIUS_LIVE_RUN_EVIDENCE.md`, run 3). No
  content-dropping failure was observed to confirm the deterministic
  coverage gate's REJECT path against a real model output; that path is
  currently verified only against hand-written test-double proposers.
- **Typography differs from hand-written fixtures.** Real output used
  Unicode dashes (`read‑only` vs. ASCII `read-only`), noun forms where a
  fixture assumed an adjective (`idempotency` vs. `idempotent`), and
  prose structure a proximity-based negation check did not anticipate
  ("Exceptions (When NOT to Retry)"). Every property oracle in this
  project was written against hand-typed fixtures first and had to be
  corrected against real output second (NR-04). **Lexical/pattern-based
  oracles validated only against synthetic fixtures should be assumed
  miscalibrated against real model output until proven otherwise.**

## Token Factory API

- **Base URL:** `https://api.tokenfactory.nebius.com/v1/`, OpenAI-
  compatible `chat/completions` schema. Every executor in this project
  (`NebiusExecutor`, `NebiusConfirmExecutor`, `LLMProposer`,
  `LLMConsolidationProposer`) uses the same shape.
- **Authentication failures:** none observed. Every call across every
  session that had `NEBIUS_API_KEY` set authenticated successfully.
- **Rate limiting (HTTP 429):** `NebiusConfirmExecutor` retries on 429
  with exponential backoff (3 attempts) — this code path exists but was
  never exercised live; no 429 was returned in any session. This project's
  live call volume (single-digit to low-double-digit calls per session,
  spread over seconds to minutes) is almost certainly too low to say
  anything about the service's actual rate limits.
- **Non-choice responses:** `confirm.py`'s executor path explicitly
  handles a response with no `choices` array, but this was defensive
  coding, not something triggered by a real response in this project's
  sessions.
- **Nothing about sustained load, cost, or quota behavior is known** —
  every session here ran a handful of calls, not a production workload.

## Local executor vs. real Nemotron

Every behavioral/confirmation/repair/consolidation path in this project
has a `LocalExecutor`/mock/test-double counterpart specifically so the
deterministic harness can be tested without a live key. Two concrete
differences observed between them, beyond the obvious "one calls a
network API and one doesn't":

- **Calibration drift between a hand-written heuristic and the real
  detector it stands in for.** `MockConfirmExecutor`'s deterministic
  confirmation heuristic (80% line overlap → `CONFIRMED`) and the real
  `SEMANTIC_REDUNDANCY` auditor check (2/3 token-Jaccard overlap) do not
  always agree on the same pair of skills — a pair can clear the real
  token-based bar comfortably while failing the mock's line-based one
  purely because of differing name/heading lines
  (`docs/L16_NEBIUS_LIVE_RUN_EVIDENCE.md`, run 5 context). A deterministic
  stand-in built to avoid a network dependency is not automatically a
  calibration match for what it stands in for, and treating a mock's
  `NO_CLUSTERS`/`REJECTED` result as equivalent to the real detector's
  verdict would be a mistake specific to this project's own test
  infrastructure, not a Nemotron finding — but it is the kind of gap that
  is easy to walk into when switching between mock and live paths on the
  same corpus.
- **The passive-context finding (above) only shows up against the real
  model.** `LocalExecutor` is deterministic and does not simulate an LLM
  ignoring context — so the single highest-severity finding in this
  project's Nemotron history (NR-03) could only have been found by
  running against the real API. The local path is sufficient for testing
  harness *logic* (does the acceptance gate compute correctly given a
  response); it cannot surface model *behavior* defects by construction.

## What this document does not establish

Cross-run and cross-version stability (every finding above comes from a
small number of sessions against one pinned model,
`nvidia/nemotron-3-super-120b-a12b`), statistical confidence on quality
or latency (sample sizes are single digits to low tens of calls per
claim), cost or quota behavior under real usage, or behavior of any other
model this project could be pointed at. "Recorded, honest operational
feedback" is the bar this document aims for — not a benchmark report.

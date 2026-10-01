# Security and Evaluation Audit — Nebius Runtime Integration

## Red Team Round 2

**Date:** 2026-09-30  
**Method:** A–D–I diagnosis, boundary validation, variant analysis  
**Scope:** Nebius/Nemotron response handling and L5 behavioral validity  
**Base:** `main` at `a7f0b51` plus the changes described here  
**Evidence:** [`artifacts/nebius/2026-09-30-behavioral-real.json`](../../artifacts/nebius/2026-09-30-behavioral-real.json)

## Threat model

- The external provider can return valid JSON with missing choices, `content: null`,
  truncated output, or output whose typography differs from local fixtures.
- The model may ignore passive methodology context and substitute its own defaults.
- The provider and model cannot modify Crucible's code, deterministic property
  oracles, task fixture, or sealed artifact after generation.
- The API credential is supplied out of band and is not stored in the artifact.

## Epistemic legend

`CODE FACT` · `PLAUSIBLE HYPOTHESIS` · `CONFIRMED BY INDUCTION` · `FALSIFIED`

## Executive summary

| ID | Severity | Level | Bucket | Finding |
|---|---|---|---|---|
| NR-01 | Medium | CONFIRMED BY INDUCTION | Reliability defect | `content: null` crashed the behavioral oracle and had equivalent unsafe paths in confirmation and proposal adapters. |
| NR-02 | Medium | CONFIRMED BY INDUCTION | Evaluation defect | The 500-token behavioral budget produced intermittent null output and truncation. |
| NR-03 | High | CONFIRMED BY INDUCTION | Evaluation-validity defect | Passive skill context did not make the mutant causal; Nemotron replaced it with default safe advice. |
| NR-04 | Medium | CONFIRMED BY INDUCTION | Measurement defect | Unicode hyphens, noun morphology, and negation scope caused false-negative property observations. |

## NR-01 — Non-text provider output crossed the trust boundary

**Surprise:** two of four real variants returned `content: null`; the first run
terminated with `AttributeError: 'NoneType' object has no attribute 'lower'`.

**Prediction:** replaying a provider response with `content: null` reaches string
operations in the behavioral, confirmation, and proposal paths.

**Induction:** falsifiable mocked-provider tests reproduced all three paths. The
behavioral oracle crashed on `.lower()`, and Bob crashed on `.strip()`.

**Fix:** validate `choices`, `message`, and `content` at each provider boundary;
return an explicit error with `finish_reason`, truncation state, and usage rather
than allowing untyped data into deterministic logic.

## NR-02 — Runtime budget truncated the evidence

**Prediction:** if 500 tokens are insufficient for this reasoning model, real
responses will end with `finish_reason=length`; raising the bound will produce
complete responses.

**Induction:** controlled calls at 500 and 2000 tokens both ended with `length`.
A four-variant run at 4000 tokens completed all responses with `finish_reason=stop`.
The default behavioral budget is therefore raised to 4000 and truncation remains
visible in every run artifact.

## NR-03 — Skill activation was assumed, not demonstrated

**Prediction:** if the model treats the skill as passive context, the polarity
mutant will still recommend bounded retries; an explicit application instruction
will make the same mutant recommend the unbounded policy.

**Induction:** the first complete real run gave P3=PASS for the mutant. With
"Apply the supplied methodology exactly", the mutant gave P3=FAIL. The final
four-way run preserves the expected differential: original and repair pass all
properties; the mutant fails P3.

## NR-04 — Provider typography broke lexical oracles

**Prediction:** real output snippets containing `read‑only`, `idempotency`, and
"Exceptions (When NOT to Retry)" will fail checks written only for ASCII
`read-only`, adjective `idempotent`, and proximity-based negation.

**Induction:** each snippet produced a red regression test. Normalizing Unicode
dashes, accepting the noun form, and limiting exception negation to explicit
denials made all tests green. Replaying the stored outputs changed the incorrect
P2/P4 failures to passes.

## Final real-runtime evidence

- Model: `nvidia/nemotron-3-super-120b-a12b`
- Provider: Nebius Token Factory
- Task digest: `sha256:b4ac1371185da240fc97385a9d5360127fa43158611dabc687e03543f1b30c20`
- Behavioral digest: `sha256:1e40526a4d496a8ab62d0ebc868d29e7dd857298bd3f4428303767b6987634c6`
- Artifact file SHA-256: `9187111ac5e59bbaf3afe1b5c967985d0e8fb11abecd47df961e1db49b762d2a`
- Result: four completed runs, zero truncations, mutant alone fails P3.

## Discarded vectors

| Vector | Result | Why |
|---|---|---|
| 500 tokens always yields null content | FALSIFIED | A controlled 500-token call returned text, but ended by length; the null behavior is intermittent. |
| Nemotron categorically refuses the unsafe mutant | FALSIFIED | Explicit activation caused the mutant to produce the unbounded policy. |
| Raising the token limit alone restores the differential | FALSIFIED | It completed responses but the passive mutant was still ignored. |

## Remaining hypotheses

- Cross-run outcome stability is not yet established; one successful run does not
  prove stability across provider/model revisions.
- Confirmation and LLM proposal paths have boundary tests but still require
  successful real end-to-end evidence.

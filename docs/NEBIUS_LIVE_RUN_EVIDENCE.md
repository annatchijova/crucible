# Nebius Token Factory — live run evidence (closes P0 blocker #1)

**Date:** 2026-10-01
**Base:** main @ 8ee5520 plus the uncommitted R3 changes present at the time of the run.

`docs/STATUS_AND_TODO.md` (2026-09-24) listed the hackathon's P0 blocker as:
every Nebius/Nemotron executor path (L5 behavioral differential, L2.5/L12
confirmation, L6 Bob proposer, L7 repair loop) was written and verified only
against `LocalExecutor`, never against the real Nebius Token Factory API.
Without one successful call, the submission does not meet the hackathon's
"working application running on Nebius Token Factory" requirement.

This document records the first real runs and closes that blocker.

## What was run

All three commands below used the real `NEBIUS_API_KEY` (no
`--local-executor`, no `--mock-confirm`). Raw output is preserved in this
directory as evidence:

| Command | Artifact | Result |
|---|---|---|
| `crucible --behave` | [`2026-10-01-nebius-live-run/behave.json`](evidence/2026-10-01-nebius-live-run/behave.json) | `"nebius_blocked": false`, 4 variants `COMPLETED` |
| `crucible tests/fixtures/readme-demo --confirm` | [`2026-10-01-nebius-live-run/confirm.json`](evidence/2026-10-01-nebius-live-run/confirm.json) | 2/2 findings `CONFIRMED` |
| `crucible --report` | [`2026-10-01-nebius-live-run/report.json`](evidence/2026-10-01-nebius-live-run/report.json) | `"nebius_blocked": false`, full L1-L7 sealed pipeline completed |

## Runtime metadata

- **Model:** `nvidia/nemotron-3-super-120b-a12b`
- **Provider:** `nebius-token-factory`
- **Base URL:** `https://api.tokenfactory.nebius.com/v1/`
- **Task ID / digest (`--behave`, `--report`):** `retry-strategy-design` /
  `sha256:b4ac1371185da240fc97385a9d5360127fa43158611dabc687e03543f1b30c20`
- **Confirmation digest:** `sha256:e587da27434d22232b0f2b45da3e8cc57a9f3ca2b5ec5a7954c85c8814152208`
- **Report digest:** `sha256:1eb55c6fe3d37662cd88e5dda5bd56e825025fed3c5cd7c6b698c17749af269d`
- All three artifacts' SHA-256 (of the file as saved here, not the internal
  seal) are recorded in git history via this commit; verify with
  `sha256sum docs/evidence/2026-10-01-nebius-live-run/*.json`.

## What this evidence establishes, and what it does not

**Establishes:** the Nebius/Nemotron wiring in `behavioral.py`, `confirm.py`,
and the `--report` pipeline is not dead code — it successfully authenticates,
sends real prompts, and parses real completions from the configured model,
for the task fixtures exercised. `nebius_blocked` being `false` in both
`--behave` and `--report` is the specific, checkable signal the local
executor cannot produce.

**Does not establish:** behavioral stability across model versions or
providers (an explicitly known limitation per the evaluation plan),
coverage of `--bob`/`--repair-loop`/`--repair-evidence` against the live API
in this same session (not re-run here; `repair_evidence.py` already has its
own contract tests but the live run above did not specifically exercise the
LLM proposer path), or anything about cost/rate-limit behavior under
sustained use.

## Key handling

`NEBIUS_API_KEY` was recovered from `~/Downloads/token_nvidia.txt` (dated
2026-09-24 — it had been generated but never wired into an environment
variable, which is why P0 blocker #1 stayed open) and written to this
repo's `.env` (gitignored, never committed — verify with
`git check-ignore -v .env`).

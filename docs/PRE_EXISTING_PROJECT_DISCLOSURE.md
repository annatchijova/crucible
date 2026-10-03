# Pre-existing Project Disclosure

**Project:** Crucible
**Repository:** https://github.com/annatchijova/crucible
**License:** Apache-2.0
**Last verified:** 2026-10-03 (`git log --oneline | wc -l`, `git log --format="%ad" --date=short`)

## Project origin

Crucible was built from scratch during the hackathon period. The first
commit (`7319b81 chore: establish repository baseline`) was made on
2026-09-23. As of this update the repository has 92 commits spanning
seven distinct days: 2026-09-23, 09-24, 09-25, 09-30, 10-01, 10-02, and
10-03. No code, tests, or documentation existed before the hackathon.

An earlier version of this document (written after the first two days)
said "all 38 commits ... on 2026-09-23 and 2026-09-24." That was accurate
at the time it was written; it is stale now that the project continued
past that point. This update corrects it rather than leaving a dated
undercount on record. The research notes in `docs/research/`
(intentionally gitignored) were also created during the hackathon.

## What was built during the hackathon

### Days 1–2 (2026-09-23 to 09-24) — Core system through L13

- L1: Corpus compiler — SKILL.md files into a versioned, source-addressable
  Skill IR with SHA-256 content digests.
- L2: Deterministic auditor, growing from an initial 14 checks to the
  current 29 (see L2 below for the current count).
- L3: Typed composition graph — composition/delegation edges, cycles,
  orphan skills, hubs, disconnected components.
- L4: Mutation laboratory — 8 seeded mutations.
- L5: Behavioral differential harness — deterministic property oracles,
  local executor, Nebius integration.
- L6: Bob workflow — rule-based proposer, deterministic re-audit.
- L7: Closed repair loop — find, repair, re-audit, replay, accept/reject.
- L8: CI workflow and read-only HTML viewer.
- L9: Style-agnostic extraction for non-RFC-2119 normative language.
- L10: Universal engineering checks (secrets, credentials, resource
  bounds, timeouts, floating-point decision paths, dependency pinning).
- L11: Public API, demo UI, Dockerfile for single-container deployment.
- L12: Nemotron confirmation extended to all engineering check classes.
- L13: Corpus-agnostic validation against 10 skills from 7 sources.
- Red-team security audit of the L11 API surface (5 findings, all fixed).

### Day 3 (2026-09-25) — Mutation lab closure, CI workflow

- Closed both outstanding mutation survivors (`EXCEPTION_REMOVAL` via the
  new `OVERGENERALIZATION` check; `EDGE_REMOVAL` by wiring the mutation
  spec to the graph's existing `ISOLATED_SKILL` property). Kill rate 6/6,
  0 survived, 2 legitimately abstained as out of scope — unchanged since.
- Added the CI workflow (`.github/workflows/ci.yml`): three jobs (test
  suite, a red-team security-regression contract, and a mutation-lab
  kill-rate gate that fails the job if kill rate drops below 6/6 or any
  mutation survives). **These jobs exist and run on every push/PR, but
  `main` has no GitHub branch-protection rule** (verified 2026-10-03 via
  `gh api repos/annatchijova/crucible/branches/main/protection` → `404
  Branch not protected`) — a failing job turns the check red but does not
  block a merge. Whether/how to turn this into an actual merge gate is
  still an open decision (`docs/STATUS_AND_TODO.md` P1 #5), not yet made.

### Days 4–5 (2026-09-30, 10-01) — Real-runtime evidence

- Red-team round on the Nebius runtime integration: found and fixed
  `content: null` crashes, truncation at low token budgets, a passive-
  context instruction-following defect, and real-output typography
  breaking lexical oracles (`docs/red-team/2026-09-30-nebius-runtime-
  red-team.md`).
- First real executions against Nebius Token Factory with
  `nvidia/nemotron-3-super-120b-a12b`: `--behave` (4 variants completed,
  no truncation), `--confirm` (2/2 confirmed on the README fixture, and
  separately 14 real confirmation responses: 2 confirmed, 12 rejected),
  `--report` (full L1-L7 pipeline sealed). See
  `docs/NEBIUS_LIVE_RUN_EVIDENCE.md`.
- R2/R3: offline replay bundle contract (acquisition, export, pinned
  replay, explicit re-evaluation) with a private SQLite journal.
- L15: deterministic recommendation (KEEP/NEEDS_CONFIRMATION/MODIFY/
  DELETE) + LLM narrator + Markdown/HTML/PDF report rendering, run live
  against Nebius end to end.

### Day 6 (2026-10-02) — External corpus, R4 repair evidence

- Ran the auditor against an independent, real-world OSS corpus
  (818 skills, github.com/mukul975/Anthropic-Cybersecurity-Skills — not
  written by this project's author): found and fixed 3 real compiler
  bugs (real YAML frontmatter parsing via PyYAML, unquoted-colon repair);
  818/818 compiled, 552 real findings. Two calibration findings
  documented from this run: `SEMANTIC_REDUNDANCY` does not underdetect;
  `DESCRIPTION_BODY_GAP` had a real false-positive pattern on workflow-
  style skills without RFC-2119 vocabulary (`docs/evidence/2026-10-02-
  mukul975-corpus-audit/FINDINGS.md`).
- R4: captured one real Nebius-backed repair-loop run end to end
  (`docs/REPAIR_EVIDENCE.md`) — a first attempt hit the repair-proposal
  token cap (`REJECTED/NO_PROPOSAL`, `finish_reason=length` at 1,000
  tokens); raising the cap to 3,000 produced a complete `ACCEPTED` run.

### Day 7 (2026-10-03) — L16 consolidation, feedback, traces, --human

- L16: a new multi-skill consolidation workflow — clusters CONFIRMED
  `SEMANTIC_REDUNDANCY` pairs into connected components, an LLM proposes
  one merged skill per cluster, a deterministic gate (redundancy-gone,
  coverage, novelty) accepts or rejects it. Includes batch mode
  (`--consolidate-all`) and auto-rewrite of structurally exact external
  references. Run live against Nebius in both single-cluster and batch
  mode, through the Python API and the actual CLI command
  (`docs/L16_NEBIUS_LIVE_RUN_EVIDENCE.md`, `docs/decisions/0020-l16-
  consolidation-scope.md`).
- Added `COMMAND_ORACLE_WITHOUT_ARTIFACT`, the auditor's 29th check
  (a command-oracle check with a bare verification verb and no named
  script/command), inspired by external reading (credited in
  `docs/SOURCES.md`'s "Engineering inspiration" section).
- Consolidated every real Nebius/Nemotron operational finding across the
  whole project into `docs/FEEDBACK.md` (the hackathon's "feedback on
  tools/models" deliverable).
- Added real activation traces to L5 property evidence (which keyword
  matched the real model output, or which were searched and absent) —
  `docs/decisions/0021-l5-activation-traces.md`.
- Added `--human`, a stdlib-only readable terminal renderer for every CLI
  report shape, with JSON fallback for anything unrecognized —
  `docs/decisions/0022-human-readable-cli-output.md`.
- Corrected two stale status-document claims found by checking the live
  code/API before acting on them rather than trusting an old note (the
  mutation survivors above were already closed on day 3; the branch-
  protection state above was previously unverified).

## What is NOT complete

The following are honestly incomplete, open, or explicitly out of reach
with current access — this section replaces an earlier version that had
drifted out of date with the work above:

1. **CI gate enforcement.** The workflow jobs described on day 3 exist
   and run, but `main` has no branch-protection rule, so a failing job
   does not block a merge. What should actually gate a merge (any
   CANDIDATE finding? only CONFIRMED? a minimum mutation kill rate?) is
   an undecided policy question, not an implementation gap.
2. **External corpus breadth.** The author's local corpus, a 10-skill
   diverse corpus (7 sources), and the 818-skill mukul975 OSS corpus have
   been run. An NVIDIA-verified-skills corpus (for interoperability) has
   not been integrated, and none of the corpora used have documented
   per-corpus licensing yet.
3. **Seeded defect ground truth beyond the 8 built-in mutations.** A
   larger, independently labeled corpus for precision/recall measurement
   is still planned, not built.
4. **Cross-model-version stability.** Every real run in this project used
   one pinned model, `nvidia/nemotron-3-super-120b-a12b` — the only
   version this project's Nebius access currently exposes. Verifying
   behavioral stability across model versions is not achievable with the
   access available as of this writing (not a deferred implementation
   task; there is nothing to compare against yet).
5. **Demo video and demo URL/test build.** Both are hackathon
   requirements and neither exists yet.
6. **Coverage-gate measurement for L16.** The consolidation workflow's
   coverage threshold (1/2 Jaccard) is a reasoned starting point; no real
   run has yet produced a case where a model actually dropped content
   for the gate to catch, so its REJECT path is verified only against
   test-double proposers, not a live failure.

## NVIDIA / Nebius usage

Nebius is integrated as the model execution provider for L5 (behavioral
differential), L2.5/L12 (confirmation), L6/L7 (Bob proposer and repair
loop), and L16 (consolidation proposer). The model is
`nvidia/nemotron-3-super-120b-a12b` via the Nebius Token Factory API.
Unlike the state at the end of day 2 (code-complete, blocked on a missing
credential), the integration has since been executed against the real
API multiple times across days 4, 6, and 7, with evidence preserved in
`docs/NEBIUS_LIVE_RUN_EVIDENCE.md`, `docs/REPAIR_EVIDENCE.md`, and
`docs/L16_NEBIUS_LIVE_RUN_EVIDENCE.md`. Every real run's scope and
limitations are stated in those documents; none of them claim
generalization beyond the runs actually performed.

## Verification

All claims in this document are independently checkable:

- `git log --oneline | wc -l` and `git log --format="%ad" --date=short`
  show the real commit count and date range.
- `PYTHONPATH=src python3 -m pytest` runs 757 tests (plus 4 skipped for
  the optional `reportlab` dependency), all passing.
- `PYTHONPATH=src python3 -m crucible.cli --mutate --human` shows the
  current 6/6 kill rate.
- `gh api repos/annatchijova/crucible/branches/main/protection` shows the
  current (unprotected) state of `main`.
- `docs/NEBIUS_LIVE_RUN_EVIDENCE.md`, `docs/REPAIR_EVIDENCE.md`, and
  `docs/L16_NEBIUS_LIVE_RUN_EVIDENCE.md` contain the raw JSON from every
  real-provider run referenced above, with digests.

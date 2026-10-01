# Next construction levels

This is a sequence of acceptance gates, not a declaration of completed levels.
Existing implementations and runtime evidence must pass their gates before a
level is called complete. Scheduling remains separate from technical readiness.

## Execution checkpoint — 2026-10-01

Destination remains methodology verification and engineering: evidence-backed
findings, compositional analysis, seeded falsifiers, behavioral comparison and
repairs admitted only through explicit deterministic gates. Filesystem hardening
is an inherited ingestion invariant, not a new product level for every patch.

The recent ingestion block (`2504836` through `175bae1`) delivered nested
independent collection scanning, bounded enumeration/reads, source identity
checks and explicit error coverage. This is an implementation milestone, not
closure of the entire input-scope gate below. Do not use test counts as a proxy
for methodological accuracy or release readiness.

| Product outcome | Evidence now | Remaining exit evidence | Work state |
|---|---|---|---|
| Audit one skill, a repository or installed packages with honest scope | Local APIs/CLI, sealed independent collection, ingestion regression cases | Shared cross-mode coverage contract, explicit roots, missing-context reporting, equivalence fixtures | Implemented in part; gate open |
| Inspect and replay a bounded model experiment without recontacting the provider | Saved real L5 four-way run; runtime metadata; deterministic local harness | Offline replay bundle with oracle identity, full observations, negative controls and source links | **Active construction block** |
| Justify findings and repair decisions independently | Seeded mutations, external-corpus fixtures, local repair loop | Held-out adjudication, class-level denominators, repeated pinned experiments, real repair evidence | Gate open; not benchmarked |
| Use and publish the complete workflow | CLI, API and read-only viewer | End-to-end user tasks, accessibility, deployment/privacy review and release evidence | Gate open; not release-ready |

### Active block: runtime evidence and replay

1. **R1 — explicit local execution:** `--report --local-executor` must keep
   confirmation local even if a provider key exists. Evidence: regression test
   forbidding provider selection with a dummy key, plus report/CLI contracts.
2. **R2 — replay bundle contract:** pin task, skill/source digests, request
   configuration, complete raw observations, runtime status and oracle identity.
   Export/import must preserve original evidence; missing/truncated inputs must
   not earn acceptance. No implicit remote calls during replay.
3. **R3 — offline replay:** reproduce observations and acceptance decisions with
   the pinned oracle, reject tampered/mismatched bundles, and distinguish replay
   from re-evaluation under a newer oracle. Keep historical outputs untouched.
4. **R4 — real repair evidence:** only after R2/R3, run the authorized provider
   path and retain a full evidence bundle, including rejected/failed outcomes.
   A favorable single run does not close independent evaluation.

R1 is locally verified by `tests/test_report_local_boundary.py`. R2 now has an
[initial storage/validation contract](REPLAY_BUNDLE.md) and executable negative
controls in `tests/test_replay_bundle_contract.py`. Opt-in executor transport capture
is covered by `tests/test_runtime_capture.py`, retaining original guidance and
actual wire bodies separately. The v2 capture-backed bundle now links these to
task/variant digests and an oracle source/runtime fingerprint; tests in
`tests/test_capture_bundle.py` cover cross-links, offline loading and continued
v1 support. Durable CLI export and interrupted-run recovery remain pending, so
R2 is not closed. R3/R4 remain pending; no real
repair run or historical-artifact conversion is claimed.

### Selection and closure discipline

- Every work block names its product outcome, prerequisite, executable exit
  evidence and preserved invariants before implementation.
- One active construction block at a time. Ingestion regressions can interrupt
  it only with a reproduced safety/correctness failure; otherwise track them
  against their open gate instead of extending hardening indefinitely.
- Per-block red team checks new claims and inherited invariants; local contract
  checks support each change. Integrated review/verification precedes release.
- Handoffs report which exit criterion moved, what evidence was produced and
  what remains open, not merely commits or number of passing tests.
- Calendar estimates are not readiness evidence. Revalidate event dates/rules
  before release planning; do not assume an old “50 days remaining” is current.

## Current closure: confirmation evidence

Both confirmation entry points now preserve runtime metadata in each sealed
confirmation entry. Truncated responses and executor errors produce UNCLEAR.
The original deterministic audit remains unchanged. Legacy executors without
runtime metadata retain explicit null metadata rather than fabricated values.
These are additive fields in `crucible-confirmation/v1`; historical artifact
digests remain historical and must not be recomputed as if they were new runs.

On 2026-10-01 a real Nebius run returned 14 complete responses: 2 CONFIRMED and
12 REJECTED, with no errors or truncations. These are model observations, not
ground-truth labels. The run printed its summary and response metadata but did
not persist its full confirmation artifact; the summary is not a replay bundle.

## Next gate: one skill, repository, installed collection

Existing API paths cover uploaded skill text, a local directory, and installed
collections. They need a common coverage contract before broader UI promises.

Implemented increment: installed scans now also search `~/.codex/skills` for
direct child packages. Successful API results include source paths, discovered,
analyzed and skipped counts, and PARTIAL coverage when duplicate package names
are omitted. Existing root precedence is retained. This coverage is API envelope
metadata, not part of the sealed audit. The independent collection mode now
discovers nested packages (including `.system`), retains homonyms and seals
COMPLETE/PARTIAL/EMPTY coverage; bounds and identity checks are documented in
the READMEs. External plugin caches/custom roots, custom Codex homes and a common
cross-mode coverage envelope remain pending. The CLI preserves
its audit-only JSON by default and warns on stderr when coverage is PARTIAL.
`--scan-installed --include-coverage` emits an envelope with `audit` and `coverage`;
coverage remains outside the audit seal.

- Report requested scope, discovered skills, analyzed skills, exclusions, and
  failures. Never equate an empty or partial scan with a clean corpus.
- Distinguish a single uploaded text from a skill package with references/assets.
  Missing context must remain visible.
- Inventory installed Codex skills alongside existing Claude/Devin locations;
  support explicit roots and test discovery using isolated temporary directories.
- Preserve source identity when names collide across roots. Report duplicates
  without silently dropping independently sourced skills.
- Make repository scanning reproducible from a local snapshot and content
  digests. Remote acquisition is a separate boundary with pinned revisions;
  scanning must not execute repository scripts.
- Bound total bytes, file count and traversal work before copying a collection.

Exit evidence: cross-mode equivalence for the same corpus; fixtures for nested
repositories, duplicate names, missing references, partial failures, symlinks,
and scan limits; every discovered item accounted for.

## Next gate: runtime evidence and replay

- Persist complete model observations and request configuration with source
  audit/IR identities, response IDs, finish reasons, usage and explicit errors.
- Keep raw historical outputs separate from re-evaluation under a newer oracle.
- Version oracle semantics and record their identity; deterministic sealing of
  an output does not imply repeatable remote generation.
- Verify incomplete responses cannot produce acceptance in behavioral replay,
  confirmation or repair. Current confirmation closure covers only one layer.
- Test malformed envelope shapes and error propagation across all consumers.

Exit evidence: an offline replay bundle, negative controls, and an end-to-end
real repair run. One successful behavioral run is not a stability benchmark.

## Next gate: independent evaluation

- Review the 14 external-corpus candidates with source evidence and explicit
  adjudication criteria, including disagreement with model opinions.
- Keep development examples separate from held-out evaluation fixtures.
- Measure class-level precision/recall and abstention on labeled fixtures.
- Test oracle false positives as well as false negatives: mentioning an
  exception is not necessarily acknowledging an exemption from a retry budget.
- Repeat pinned model experiments to estimate variation instead of selecting
  a single favorable result.

Exit evidence: reproducible evaluation with denominators, provenance, failure
cases and limitations. Do not tune the evaluation to reproduce an expected demo.

## Next gate: usable product

Present scope selection, scan progress, coverage, evidence-backed findings,
optional external confirmation, and replay/export as distinct user actions.
Make loading, empty, partial, failed and completed scans distinguishable.

Exit evidence: an end-to-end task for each input mode, accessible navigation,
clear findings tied to source locations, and an accurate local/offline mode.

## Release gate

Repeat adversarial checks across ingestion, provider responses, oracle semantics,
repair acceptance and rendering. Public hosting needs its own authority, path
access, resource and privacy review; a local directory endpoint is not evidence
that public deployment is safe. Record corpus licensing and deployment evidence.

# Next construction levels

The time-bounded execution sequence is in [the 27-day build plan](27_DAY_BUILD_PLAN.md).

This is a sequence of acceptance gates, not a declaration of completed levels.
Existing implementations and runtime evidence must pass their gates before a
level is called complete. Scheduling remains separate from technical readiness.

## Execution checkpoint — 2026-10-02

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
| Inspect and replay a bounded model experiment without recontacting the provider | Saved real L5 run; v2 bundles with source/oracle links; journal, export, pinned replay and explicit re-evaluation | Integrated release verification; repeated/held-out repair evaluation | **R1–R4 exercised locally/live; two accepted synthetic L7 captures, one v2 decision replay MATCH** |
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
   the pinned oracle (property decisions are PASS/FAIL/ABSTAINED), reject
   tampered/mismatched bundles, and distinguish replay from re-evaluation under
   a newer oracle. Keep historical outputs untouched. The general
   `crucible-replay-bundle/v2` does not carry L7 repair-decision inputs; the
   separate repair-evidence bundle now has its own offline L7 replay path.
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
v1 support. Optional SQLite journaling now retains committed captures across
process interruption, with explicit partial-state inspection and no automatic
provider retries (`tests/test_capture_journal.py`). The CLI now exposes separate
`--capture-replay`, `--inspect-replay` and `--export-replay` modes with explicit
exit codes, no implicit retries and no provider calls on read/export. Evidence:
`tests/test_replay_cli.py` and the [scoped review](red-team/2026-10-01-replay-cli.md).
R2's bounded storage/acquisition/export gate is locally verified for the current
four-way Nebius adapter. This is not a live-provider rerun or global recovery
guarantee. R3 has separate pinned replay and explicit re-evaluation CLI paths.
They recompute per-property observations offline and seal a new result without
changing the bundle. The [R3 review and negative controls](red-team/2026-10-01-r3-replay-code-review.md)
close local R3 verification under its stated trust assumptions. The R3
behavioral-bundle replay reports per-property agreement; it remains separate
from the repair-evidence replay that reconstructs L7 acceptance.
R4's private capture path and local negative controls are implemented in
`repair_evidence.py`. On 2026-10-02, the first live fixture response ended with
`finish_reason=length` at the 1,000-token cap and was retained as
`REJECTED / NO_PROPOSAL`. After increasing the shared cap to 3,000, a second
capture returned `ACCEPTED`: the targeted finding disappeared, no new findings
appeared, and the seeded behavioral property changed from FAIL to PASS. On
2026-10-07, an accepted loop-v2 run was captured at
`/tmp/crucible-l7-live-20261007-04`; all three responses were complete and the
new `--replay-repair-evidence` command returned `MATCH` without contacting
Nebius. Earlier captures that used the pre-fix proposal prompt correctly return
`NOT_REPLAYABLE` under the current prompt. The accepted evidence is still one
synthetic task and one model session, not evidence of general repair accuracy
or stability. Independent evaluation and integrated release verification
remain open. See the
[L7 evidence contract](REPAIR_EVIDENCE.md) and [27-day plan](27_DAY_BUILD_PLAN.md).

L7 correctness increment: the ordinary repair loop is now version 2. It rejects
length-limited or metadata-incomplete Nebius proposals before re-audit and
returns `ERROR / INCOMPLETE_PROVIDER_RESPONSE` if either behavioral response
cannot support an observation. A response is usable only with stop completion,
no truncation, nonempty output/response ID, and consistent usage counts. Local
contract tests and one live-capture/replay pair verify the current integration
end to end for the built-in synthetic task. This is not a stability estimate
or independent repair evaluation.

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

Increment: uploaded-text and local-directory API results now expose the same
coverage count keys (`scope`, `status`, `discovered`, `analyzed`, `skipped`,
`errors`) as installed direct-child scans. These fields describe input
accounting and remain outside the sealed audit. This does not yet unify the
independent nested-collection envelope, expose exclusions by reason in every
mode, or establish cross-mode equivalence for arbitrary directory layouts.

Nested-repository fixture: `scan_directory()` now allows `compile_corpus()` to
perform its bounded recursive discovery instead of rejecting repositories
whose `SKILL.md` files sit below a grouping directory. A two-package nested
fixture yields matching discovered/analyzed counts in directory and independent
collection modes. Installed direct-child mode intentionally has narrower scope;
this fixture does not claim equivalence for that mode.

Explicit-root increment: local Python callers can pass roots to both
`scan_installed_skills(roots=...)` and `scan_installed_collection(roots=...)`.
The shared validator rejects missing paths, files, symlink roots, duplicate
roots, scalar/empty arguments, and lists above 256 entries. Default root
selection is unchanged. The collection artifact now seals its searched roots
and common coverage fields as `crucible-installed-collection/v2`; historical
v1 artifacts are not rewritten. The CLI exposes repeated `--scan-root DIR`
for exactly one installed mode; the HTTP route continues to use standard roots.
Automatic custom Codex-home discovery remains open.

Implemented increment: installed scans now also search `~/.codex/skills` for
direct child packages. Successful API results include source paths, discovered,
analyzed and skipped counts, and PARTIAL coverage when duplicate package names
are omitted. Existing root precedence is retained. This coverage is API envelope
metadata, not part of the sealed audit. The independent collection mode now
discovers nested packages (including `.system`), retains homonyms and seals
COMPLETE/PARTIAL/EMPTY coverage; bounds and identity checks are documented in
the READMEs. Automatic external plugin/custom Codex-home discovery and a common
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

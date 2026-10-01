# Next construction levels

This is a sequence of acceptance gates, not a declaration of completed levels.
Existing implementations and runtime evidence must pass their gates before a
level is called complete. Scheduling remains separate from technical readiness.

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
metadata, not part of the sealed audit. Nested system/plugin collections, custom
Codex homes, empty/error coverage envelopes, and CLI display of coverage remain
pending; the legacy CLI currently projects only the audit.

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

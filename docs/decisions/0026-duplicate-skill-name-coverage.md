# ADR-0026 — Refuse or report a colliding skill name, never discard the corpus

**Date:** 2026-10-23  **Status:** Accepted; implemented in this change
**Reversibility:** low for the schema (`skill-ir/v2` published in-repo); the
policy parameter is additive and removable.

## Forces at the time

- Selecting a held-out corpus by metadata produced
  `vantaflow/claude-skills-collection` @ `f88a34d0`, 696 skills, MIT. It could
  not be compiled at all: `compile_corpus` raised on four duplicate declared
  names and discarded all 696 skills.
- The four collisions are two distinct cases. `ultra-concise-mode` and
  `workflows` are byte-identical files republished under a second category
  path. `conflict-resolver` (6228 vs 13104 bytes) and `monitoring-setup`
  (8115 vs 8666 bytes) are different methodologies that happen to declare the
  same name.
- The analysis layers key skills by name: `graph.py` resolves edge targets
  against a name set, the auditor builds `skill_by_name`, and L16
  consolidation rewrites references by exact name match. Name uniqueness
  inside one compiled artifact is a real requirement, not an accident.
- `api.py:scan_installed_collection` already documents that "names need not be
  globally unique" and already reports per-item `SKIPPED_DUPLICATE` with
  `EMPTY`/`PARTIAL`/`COMPLETE` coverage. A scan of 299 installed skills
  reports 198 skipped. The directory-corpus path had no equivalent and
  aborted instead.

## Decision

Keep name uniqueness inside the compiled artifact, and stop making an
all-or-nothing choice between it and analyzing the corpus.

`compile_corpus` gains `on_duplicate_name`. The default `ON_DUPLICATE_ERROR`
preserves the existing refusal exactly, so no caller changes behaviour
silently, and the message now names its own opt-in and the CLI flag that
enables it. The explicit `ON_DUPLICATE_SKIP` (CLI `--skip-duplicate-names`)
keeps the first skill by sorted source path and records every exclusion.

The IR gains `excluded`, **always present**, empty for a clean corpus. Each
entry names the dropped path, its digest, the path that survived, and a
reason distinguishing the two cases: `DUPLICATE_NAME_IDENTICAL_CONTENT`, where
nothing analysable was lost, from `DUPLICATE_NAME_DISTINCT_CONTENT`, where a
real methodology was dropped. A reader cannot otherwise tell whether 692 of
696 is complete coverage or a silent loss of four methodologies.

Which skill survives is ordered by sorted source path, so it does not depend
on filesystem traversal order and the artifact digest stays reproducible.

## Consequences accepted

- `SCHEMA_VERSION` moves to `skill-ir/v2`; every IR, audit and graph digest
  changes. `graph.py` was comparing a hardcoded `"skill-ir/v1"` instead of
  importing `SCHEMA_VERSION`; that is now fixed, which is why this change
  initially failed far more tests than the three version assertions it should
  have.
- The strict default means a colliding corpus still needs an explicit operator
  decision. That is intended: refusing ambiguous input is better than quietly
  analyzing 692 of 696, and the error now tells the operator exactly how to
  proceed.
- Corpus-root compilation failures are now reported as `error: ...` with exit
  1, matching the scan modes, instead of a traceback that buried the remedy.
- The surviving skill in a homonym collision is arbitrary with respect to
  quality. Sorted source path is deterministic, not a judgement that the kept
  methodology is the better one.

## What this does not do

- It does not make the corpus fully analyzable. Two real methodologies in
  `vantaflow` remain unanalyzed; the artifact says so rather than hiding it.
- It does not give the analysis layers homonym support. Keying skills by
  source path instead of name would be the deeper fix and is deferred: it
  touches the graph name set, the auditor's name index and L16's rewrite path.
- It does not change any detection heuristic. No finding for any individual
  skill differs because of this change.

## Consumption consequence

The defect was found by compiling `vantaflow`, so that corpus informed this
implementation. Under ADR-0025's sibling rule in `corpus_provenance.py`, a
`HELDOUT_SEALED` corpus may record no consumption. `vantaflow` is therefore
sealed `TUNING_CONSUMED`, naming this fix, and is not available for a
generalization claim. `nimadorostkar/Claude-Skills-collection` compiled clean
and taught the implementation nothing, so it remains `HELDOUT_SEALED`. A
replacement held-out corpus is still required.

## Rejected alternatives

- **Deduplicate byte-identical files silently and error only on homonyms.**
  Rejected: it still refuses `vantaflow`, and silent deduplication hides that
  the corpus publishes the same skill twice.
- **Make names non-unique and key everything by source path.** The
  architecturally correct fix and a much larger one, across the graph, auditor
  and consolidation. Deferred rather than rejected.
- **Append a disambiguating suffix to colliding names.** Rejected: it
  fabricates an identity no source declares, and L16 would then rewrite
  references to a name that exists nowhere in the corpus.
- **Add `excluded` only when skipping is enabled.** Rejected: an artifact that
  omits the field when coverage is complete is indistinguishable from one
  written before the field existed, so a reader cannot tell silence from
  completeness.

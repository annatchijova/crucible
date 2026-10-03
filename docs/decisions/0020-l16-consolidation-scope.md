# ADR-0020: L16 Skill Consolidation Scope

**Status:** Accepted
**Date:** 2026-10-03
**Reversibility:** high; the workflow is additive, no existing check or
artifact schema changed

## Context

L15's recommendation module answers "delete this skill" for a skill with a
CONFIRMED redundancy finding, keeping the other member of the pair
untouched. The user asked for more: when a *group* of skills are mutually
redundant ("si hay 15 skills más o menos de lo mismo, hacer 1"), have an
LLM analyze the group and propose one merged skill replacing all of them —
with the explicit instruction to keep this disciplined and incremental,
not a new subsystem ("no necesitamos revolucionar nada... sigamos con más
disciplina").

This is architecturally the same pattern as the Bob workflow (L6) and the
closed repair loop (L7): the LLM proposes, a deterministic layer decides.
Three things are genuinely new and needed their own decision:

1. Going from pairwise CONFIRMED findings to a cluster of 2+ skills.
2. What to do when a skill outside the cluster references a member by
   name (composition references join on name string, with no stable ID —
   see `auditor.py::_check_broken_references`).
3. Verifying the merge actually kept everything the originals declared,
   since there is no existing "did the merge keep everything" check.

## Decision

Add `src/crucible/consolidation.py` (L16): `find_redundancy_clusters` +
`find_external_references` + `ConsolidationProposer` protocol +
`LLMConsolidationProposer` + a deterministic acceptance gate
(`run_consolidation`), wired via a new `--consolidate` CLI flag.

### Clustering source: SEMANTIC_REDUNDANCY only

`STRUCTURAL_REDUNDANCY` already has its own single-skill repair path in
`bob.py` (differentiate the duplicate via a description note). Mixing a
second, differently-shaped redundancy signal into clustering would blur
which rule justified grouping which skills — each check class should
independently justify its own action, the same principle
`recommendation.py`'s docstring already states for DELETE. A pair becomes
a cluster edge iff its one `SEMANTIC_REDUNDANCY` finding (emitted once per
pair) has verdict `CONFIRMED` in the L2.5 confirmation artifact — a
CANDIDATE alone is never enough, or the LLM's confirmation judgment would
never have entered the decision path.

Clustering reuses `graph.py::_find_components` (a generic union-find
already used to detect disconnected graph components) over synthetic
edges built from confirmed pairs, instead of writing a second
connected-components implementation.

### External references: refuse the whole cluster's merge

**Asked the user directly; they chose refuse over auto-rewrite.** If any
skill outside the cluster references a member by name (via
`build_composition_graph`'s edges — both section-heading and
description-text relations), the merge is rejected outright
(`EXTERNAL_REFERENCE_BLOCK`), reporting exactly which external skill
references which cluster member. Auto-rewriting referrers outside the
cluster is out of scope for this increment: it would touch files outside
the cluster, compounding blast radius, and would need its own independent
acceptance gate. Noted here as explicit future work, not silently dropped.

### Coverage threshold: a new, separately-justified constant

`_COVERAGE_THRESHOLD = Fraction(1, 2)`, distinct from `auditor.py`'s
`_SEMANTIC_THRESHOLD` (2/3). The 2/3 bar is calibrated to *detect* two
comparably-sized documents as duplicates — strict, to avoid false
redundancy claims. Coverage asks the inverse question: does the (larger)
merged document still contain this one original rule's or check's
content? A single short rule's token set, diluted against a merged
document covering N skills' worth of rules and checks, will not clear 2/3
even when the content is genuinely present. 1/2 is a deliberate,
independently-justified, revisable choice — not borrowed from the
existing threshold for convenience. Every unmatched rule/check is reported
by name (`source_skill`, `item_type`, `item_text`, `best_overlap`): a
falsifiable gap list, not a pass/fail black box.

### Novelty check, adapted for a merge

The merged skill has a NEW name, so its findings cannot be compared by
exact `(class, skill)` pair against the originals — that pair never
existed before by construction. A finding on the merged skill is
"already known" if any cluster member had a finding of the same *class*
(redundancy classes excluded, since the redundancy-gone check above
already evaluates those with sharper semantics). A finding on any other,
unrelated skill is still compared by the exact pair, since removing N
skills and adding one can have corpus-wide ripple effects (a newly broken
reference, a newly orphaned skill).

### No behavioral gate — explicit, not omitted

`behavioral.py`'s property oracle (L5) is hand-built for one synthetic
retry-budget fixture; there are no property definitions for arbitrary
real-world skill content, so it cannot meaningfully gate a merge of real
skills. Every report carries `"determinism_level":
"deterministic_text_only"` and `"behavioral_gate": None` explicitly, so
this workflow never silently reads as L7-equivalent rigor.

### Proposer shape

A new `ConsolidationProposer` protocol (`propose_merge`, multi-skill
input) distinct from `bob.py`'s single-skill `Proposer` — merging prose
is inherently generative, so no rule-based template ships. The test
double (`NaiveConcatProposer`) lives only in the test file, explicitly
docstring-labeled as not a real engineering proposer, so it can never be
mistaken for a shippable option.

## Alternatives rejected

- **Auto-rewrite external references.** Rejected for this increment per
  direct user decision; real near-term follow-up once the refuse path is
  proven on real corpora.
- **Reuse the 2/3 semantic threshold for coverage.** Rejected: the two
  thresholds answer different questions (detect duplication vs. verify
  retention) and conflating them would miscalibrate one of them silently.
- **Batch mode (consolidate every cluster in one call).** Deferred, not
  bundled: `--cluster-index` mirrors the existing `--finding-index`
  single-target convention (`bob.py`/`repair_loop.py`); looping over every
  cluster is a natural near-term extension, not required for a first,
  disciplined increment.
- **A rule-based (non-LLM) merge proposer.** Rejected: merging prose from
  N skills into one coherent document is a generative task; no
  deterministic template captures it honestly.

## Consequences

Accepted now:
- `src/crucible/consolidation.py`: clustering, external-reference
  precondition, coverage check, novelty check, `run_consolidation`.
- `--consolidate` / `--cluster-index` CLI flags, following the existing
  flat if-chain and `--mock-confirm` conventions.
- 8 new falsifiable tests (`tests/test_consolidation_contract.py`):
  clustering, unconfirmed-pair exclusion, no-confirmation-no-clusters,
  external-reference block, coverage gap, acceptance, blocked proposer,
  determinism. Full suite green, no regressions.
- Every report is explicit about what it did NOT check (no behavioral
  gate, no external-reference rewrite).

Deferred:
- Auto-rewrite of external references.
- Running `LLMConsolidationProposer` against a real Nebius API key and
  measuring the coverage threshold against real near-duplicate corpora
  (1/2 is a reasoned starting point, not a measured one yet).

## Addendum 2026-10-03: batch mode

Added `run_consolidation_batch` / `--consolidate-all`, the batch mode
deferred above. Clusters are computed once, upfront (they are disjoint
connected components, so merging one cannot add or remove members from
another), but each cluster's gate still runs against a *freshly
re-audited* corpus rather than reusing the first pass's `(ir, audit)` --
a confirmation artifact's `finding_id`s are only valid against the audit
they were confirmed from, and go stale the moment an earlier merge
changes the corpus. The gate logic itself was extracted into
`_run_gate_for_cluster(corpus, ir, audit, cluster, proposer, context)` so
both `run_consolidation` (single, resolves `cluster_index` via
confirmation) and `run_consolidation_batch` (loops, already knows each
`cluster`) share the exact same acceptance criteria -- no duplicated gate
logic between the two entry points.

A rejected, blocked, or errored cluster is left unmerged and does **not**
block the rest of the batch: this is a batch of independent attempts, not
a transaction. `batch_status` (`NO_CLUSTERS` / `COMPLETED`) answers "did
we attempt every cluster", not "did every merge succeed" -- per-cluster
outcomes are in `reports`.

Found and fixed one real bug while wiring this in: `--cluster-index`'s
`None`-default fix from the single-cluster CLI flag did not need
revisiting, but `--consolidate-all` (a plain `store_true`, default
`False`) needed the same scrutiny against the replay-mode mutual-
exclusivity check in `cli.py` -- confirmed safe since `False` is excluded
by that check's `value is not False` test.

4 new falsifiable tests: two independent clusters both merge, one
rejected cluster doesn't block the other, no-clusters status, batch
determinism. Full suite green (738 tests), no regressions.

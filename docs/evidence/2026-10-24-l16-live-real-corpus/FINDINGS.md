# L16 consolidation on a real third-party corpus, with the real model

**Date:** 2026-10-24  **Branch:** `main`
**Corpus:** `vantaflow/claude-skills-collection` @ `f88a34d0f75e`, sealed
`TUNING_CONSUMED`. Not a generalization claim.
**Model:** `nvidia/nemotron-3-super-120b-a12b` via Nebius Token Factory,
temperature 0. Six live calls total.
**Status:** first L16 evidence outside the built-in synthetic fixture.

## Why this run

Every piece of model evidence in the repository came from one synthetic
fixture. The product claim a reader cares about is narrower and more concrete
than "audits methodologies": that the agent can say *these two skills are the
same, here is one that replaces them*, with a deterministic gate deciding
whether the merge is acceptable. That had never been shown on skills someone
else wrote.

`vantaflow` makes it testable because its 337 `SEMANTIC_REDUNDANCY` findings
are true positives: the corpus publishes each skill twice, once bare and once
category-prefixed
([measurement](../2026-10-23-redundancy-evidence-denominator/FINDINGS.md)).

## What the clusters actually look like

Union-find over the 337 confirmed pairs, across 674 of the corpus's 692
skills:

| Cluster size | Count |
|---|---|
| 2 | **337** |
| 3 or more | **0** |

Every cluster is a pair. Lowering the Jaccard threshold does not change this:
on the author's own 101 skills there are **zero** pairs even at 1/3, and on
`mukul975`'s 818 skills a 1/3 threshold yields 12 pairs with a largest cluster
of 3.

This bounds a capability the system has in code but no measured corpus
exercises. `run_consolidation_batch` clusters by connected component and would
merge ten skills if ten were connected; nothing in 2806 real skills connects
more than three. Whole-fingerprint Jaccard measures *whole-skill* similarity,
and two skills on the same topic by different authors differ too much in full
text. Merging ten needs a different similarity object, not a different
threshold — recorded as
[L5 in the research agenda](../../../INVESTIGAR-CRUCIBLE.md).

## The complete chain, with the model real at every model step

A four-skill slice of the corpus (`bug-debugger`, `dev-bug-debugger`,
`debugger`, `prompt-debugger`), audited fresh, then:

1. **L2.5 confirmation, real Nemotron.** 2 of 2 candidates `CONFIRMED` in
   6.7 s, with rationales naming the shared content ("Both skills share
   identical description, triggers, and step-by-step bug-debugging
   methodology").
2. **L16 proposal, real Nemotron.** One merge proposed per cluster.
3. **Deterministic gate.** One accepted, one refused.

| Cluster | Proposed name | Outcome | Why |
|---|---|---|---|
| `debugger` + `prompt-debugger` | `prompt-diagnostic` | **ACCEPTED** | no coverage gap, no new finding, redundancy resolved |
| `bug-debugger` + `dev-bug-debugger` | `structured-bug-debugger` | **REJECTED** | `new_findings: ["STRUCTURAL_REDUNDANCY"]`, `redundancy_resolved: false` |

**The rejection is the result worth keeping.** The gate is not a rubber stamp:
the model produced a merge that looked plausible, introduced a defect the
originals did not have, and failed to resolve the redundancy it was asked to
fix. The deterministic check refused it without a human in the loop and
without the model getting a vote.

## Direct evidence of model non-determinism

The repository has carried "one run does not establish stability" as a caveat
since the beginning, without evidence for it. There is evidence now.

The `bug-debugger` + `dev-bug-debugger` cluster was run twice against the same
inputs at temperature 0:

| Run | Response ID | Proposed name | Outcome |
|---|---|---|---|
| full corpus, mock confirmation | `chatcmpl-db03ae4f…` | `structured-bug-debugger` | ACCEPTED |
| four-skill slice, real confirmation | `chatcmpl-9e2b1581…` | `structured-bug-debugger` | **REJECTED** |

Same cluster, same model, same temperature, same proposed name, opposite
verdict. The two runs differ in the corpus context passed to the proposer, so
this is not a controlled determinism test and does not isolate the cause. What
it does establish is that a single accepted L16 run is not evidence that the
path reliably produces acceptable merges, which is exactly what the caveat
said and could not previously show.

## Independent verification of the accepted merges

The gate's own claims were re-checked rather than trusted, by recompiling the
merged text and comparing against the originals:

| Check | `debugger` cluster | `bug-debugger` cluster (full-corpus run) |
|---|---|---|
| distinct original rules missing verbatim | 0 of 1 | 0 of 1 |
| distinct original checks missing verbatim | 0 of 10 | 0 of 0 |
| classes in the merge absent from both originals | none | none |

`new_findings: []` was confirmed independently: the merged skill inherits
exactly the classes an original already had.

## Limits

- **The coverage gate was weakly exercised on one cluster.** `bug-debugger`
  and `dev-bug-debugger` carry 1 rule and 0 checks between them, so
  "no coverage gap" is a low bar there. The `debugger` cluster, with 10
  distinct checks, is the one that tested it.
- **The two full-corpus runs used the deterministic mock confirmation**, not
  the model, to produce their clusters. Only the four-skill slice has the
  model at every model step.
- **All clusters are pairs**, so nothing here demonstrates merging a larger
  group; see the bound above.
- **No behavioral gate.** L16 is deliberately text-only; L5's property oracle
  does not generalize beyond its one synthetic task, and every report says
  `"behavioral_gate": null`.
- **`vantaflow` is `TUNING_CONSUMED`.** Two accepted merges and one refusal on
  one corpus establish that the path runs on third-party skills, not an
  acceptance rate.
- **Six calls.** Nothing here is a cost or latency estimate; the chain took
  6.7 s to confirm and about 16 s per proposal on one occasion each.

## Reproducing

The proposals and the merged skill texts are source-derived material and stay
private under the corpus licensing rule, as with every other `vantaflow`
artifact. The chain is reproducible from the sealed corpus manifest plus the
response IDs recorded above; model output is not reproducible by nature, which
is the point of the preceding section.

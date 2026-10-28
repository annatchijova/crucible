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

**Correction, same day.** This record first read the rejection as the gate
catching a real defect: "the model produced a merge that introduced a defect
the originals did not have". That was wrong, and investigating it found two
defects in the gate instead. Both are recorded below as G-01 and G-02. The
merge was refused for reasons that do not describe it.

## G-01 — a corpus-level finding re-anchors after a merge and is read as new

`STRUCTURAL_REDUNDANCY` is a corpus-level pairwise finding: its evidence reads
*identical rule text appears in 2 skill(s): X, Y*, and it is attributed to one
member of the pair. Replaying the refused merge through the gate's own
comparison:

| | attributed to | pair named in the evidence |
|---|---|---|
| before the merge | `dev-bug-debugger` | `dev-bug-debugger`, `prompt-debugger` |
| after the merge | **`prompt-debugger`** | `prompt-debugger`, `structured-bug-debugger` |

The duplication is the same text in both cases -- the boilerplate
`Communication Rules` block this corpus repeats 302 times. It did not appear;
it **moved**, because the skill it had been attributed to was consumed by the
merge.

`_find_new_findings` compares a finding on any skill outside the cluster by
exact `(class, skill)` pair, so `("STRUCTURAL_REDUNDANCY", "prompt-debugger")`
is unseen and therefore new. The function's own docstring anticipates
corpus-wide ripple effects and treats them as real; this is the case where
that assumption produces a **false rejection**. The merge introduced nothing.

This only fires when the cluster participates in a corpus-level relationship
with a skill outside it, which is why the full-corpus run of the same cluster
was accepted: there, `STRUCTURAL_REDUNDANCY` belonged to
`agent-a2a-protocol-guide`, unrelated to the cluster and undisturbed by the
merge.

## G-02 — `redundancy_resolved` is corpus-wide, not cluster-scoped

The same refused merge reports `redundancy_resolved: false`. The redundancy
remaining after it is `debugger` / `prompt-debugger` at a 98/107 token overlap
-- the **other** cluster in the slice, untouched by this merge. The merge did
resolve its own redundancy: `bug-debugger` and `dev-bug-debugger` are gone.

So a corpus holding any other unresolved redundancy pair can make every merge
in it report `redundancy_resolved: false`, independently of whether the merge
worked. On a corpus like `vantaflow`, with 337 redundancy pairs, that is the
normal case rather than the exception.

## What the two gate defects cost

The gate still refuses proposals, and refusing on a wrong reason is safer than
accepting on a wrong reason. But the demonstration is weaker than first
written: of the two refusals observed, the one examined in detail was a false
rejection, so this run does not show the gate catching a defect the model
introduced. It shows the gate is not a rubber stamp, and that two of its
signals are corpus-sensitive in ways that do not describe the merge under
test.

Neither defect is patched here. Both are acceptance-gate semantics, the build
is green five days from a submission, and the fix for G-01 means comparing a
corpus-level finding by its own identity -- the duplicated text and the set of
skills it spans -- rather than by the skill it happens to be attributed to.
That is a design change, not a one-line guard.

**Update, 2026-10-28.** G-01 and G-02 are fixed, together with a third defect
of the same kind (G-03). The G-02 diagnosis above was wrong about the
mechanism: the field was simply `outcome == ACCEPTED`. See
[the gate fixes](../2026-10-28-l16-gate-fixes/FINDINGS.md), which also replays
this slice without a model.

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
verdict. G-01 above explains the difference, and it is not model noise.

A **controlled** test was then run: the same cluster, the same four-skill
corpus context, the same audit digest, twice.

| Run | Proposed name | Proposal text | Outcome | Reason |
|---|---|---|---|---|
| 1 | `structured-bug-debugger` | `sha256:23800ed6…`, 5659 B | REJECTED | `NEW_FINDINGS` |
| 2 | `unified-bug-debugger` | `sha256:70d93b15…`, 5661 B | REJECTED | `NEW_FINDINGS` |

The model is **non-deterministic at temperature 0**: different text, different
chosen name, on identical input. The gate's verdict, its reason, and the
finding it named were **identical across that variation**. That is the
architectural claim the project makes, tested directly for the first time: the
narrator varies, the decision does not.

It remains true that one accepted run is not evidence of a reliable path. What
changed is the reason: the earlier opposite verdicts were a gate defect, not
proof of unstable acceptance.

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

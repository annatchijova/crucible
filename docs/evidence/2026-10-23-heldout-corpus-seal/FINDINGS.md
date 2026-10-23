# Held-out corpus selection and seal

**Date:** 2026-10-23  **Branch:** `main`
**Status:** one corpus sealed held-out; one reclassified as consumed; a
replacement is still required.

## Why selection criteria come first

`docs/27_DAY_BUILD_PLAN.md` days 1-5 require reserving independent skills for
evaluation and not tuning on the examples used to claim performance.
`corpus_provenance.py` makes that failure-closed: `HELDOUT_SEALED` rejects any
recorded consumption.

That creates a selection constraint which is easy to violate by accident.
Choosing a corpus by its rule-extraction yield, its finding count or its edge
count means selecting on the very variable the corpus is reserved to measure,
and the held-out set is invalidated before it is used. So selection used
metadata only.

## Criteria applied, and the evidence for each

| Criterion | How it was checked |
|---|---|
| Independent authorship | `gh repo view` for fork status and parent; no fork, no parent for any candidate |
| Not a republication of a consumed corpus | skill directory-name overlap against the 818 `mukul975` names and the 101 author names: 0 and 0 for the selected candidates |
| License present and identified | root `LICENSE` file listed via the contents API, and `repos/{r}/license` returning a SPDX id |
| Size supports class-level denominators | `SKILL.md` count from the recursive git tree API |
| Structural validity | compilation only, which produces no findings |

**Deliberately not examined before sealing:** modality keyword usage, rule or
check counts, audit findings, graph edges, or any Crucible output other than
whether the corpus compiles.

One API discrepancy is worth recording: `gh search repos` reported `mit` for
all five candidates while `gh repo view --json licenseInfo` reported `NONE`
for all five. Reading the repository contents resolved it; a root `LICENSE`
exists in each and the REST license endpoint returns `MIT`. Neither search
field was trusted on its own.

## Sealed corpora

| Corpus | Commit | Skills | Role | Seal |
|---|---|---|---|---|
| [`nimadorostkar/Claude-Skills-collection`](https://github.com/nimadorostkar/Claude-Skills-collection) | `238b95e2aff2` | 138 | `HELDOUT_SEALED` | `sha256:0843f779…` |
| [`vantaflow/claude-skills-collection`](https://github.com/vantaflow/claude-skills-collection) | `f88a34d0f75e` | 692 of 696 | `TUNING_CONSUMED` | `sha256:19674c5b…` |

Full records: [`nimadorostkar-claude-skills-collection.json`](nimadorostkar-claude-skills-collection.json)
and [`vantaflow-claude-skills-collection.json`](vantaflow-claude-skills-collection.json).
Both reproduce `MATCH` on recompilation. The recorded commit is a claim the
seal binds but does not verify.

## Why vantaflow is consumed, not held out

`vantaflow` was selected as a held-out corpus and could not be compiled: four
duplicate declared names made `compile_corpus` discard all 696 skills. Fixing
that was driven by synthetic fixtures, but the defect was found by compiling
this corpus, so this corpus informed the implementation. Under its own rule a
`HELDOUT_SEALED` record may name no consumption, so the honest classification
is `TUNING_CONSUMED`, naming
[ADR-0026](../../decisions/0026-duplicate-skill-name-coverage.md).

Reclassifying it is the cost of the finding, and the finding is the argument
for the practice: a corpus reserved for evaluation located a hard ingestion
failure on real input within minutes of selection, before any accuracy
measurement was attempted.

`vantaflow` now analyzes 692 of 696 skills with four recorded exclusions: two
byte-identical republications, where nothing analysable was lost, and two
homonyms, where a real methodology was dropped.

## Candidate excluded on inspection

`lionelsimai/claude-skills-collection` (5149 skills, MIT, 31 stars) was
rejected. Its tree holds 5149 `SKILL.md` files among 5153 blobs, and the
repository was created and pushed on 2026-02-08 and never touched again. A
corpus that is almost entirely `SKILL.md`, produced in one push, is far more
consistent with bulk generation than with authored methodology. Measuring
against it would estimate performance on machine-generated text. This is a
judgement from repository metadata, not a verified claim about how the files
were produced.

`mhylle/claude-skills-collection` (34 skills) and `fal3/claude-skills-collection`
(13 skills) are independent and MIT but too small for class-level
denominators. `fal3` remains a candidate for domain diversity only, since its
scope is Swift and Apple platforms rather than the security-heavy corpora
already in hand.

`abubakarsiddik31/claude-skills-collection` (1106 stars) was rejected on two
grounds: no license file, and a self-described curation of "official and
community-built" skills, which does not establish independent authorship.

## What remains open

- One replacement held-out corpus, selected under the same metadata-only
  criteria, to restore two independent evaluation corpora.
- 138 skills in the single sealed held-out corpus is thin for per-class
  denominators. Class-level precision claims should wait for the replacement.
- Nothing in this record measures detection quality. No audit was run on
  either corpus for this record.

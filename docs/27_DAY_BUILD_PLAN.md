# Crucible — 27-day build plan

**Purpose:** reach the strongest coherent, demonstrable state in the remaining
27 days. This plan uses relative days so it remains valid if the calendar
deadline moves. It does not change the product thesis or lower the evidence
bar.

## Target outcome

Demonstrate one complete, inspectable path on an independently authored skill:

```text
bounded corpus + explicit coverage
  → source-linked candidate finding
  → evidence-based disposition (confirm / reject / unresolved)
  → optional repair proposal
  → deterministic re-audit + behavioral replay
  → sealed, exportable evidence with limitations
```

The demo must make clear which steps are deterministic, which involve a model,
and what each result establishes. `CANDIDATE` remains an invitation to inspect;
model confirmation is an observation, not ground truth; repair acceptance does
not establish general correctness.

## Progress

- **Evaluation basis:** pinned the external corpus checkout to
  `54a798831d2266a3ca61ce68a7acb80b81160d57`; recorded its clean worktree and
  produced a [per-skill license-file inventory](evidence/2026-10-02-mukul975-corpus-audit/license-inventory.json).
  Terms are not yet manually reviewed, so public redistribution of source-derived
  material is not cleared.
- **First adjudication artifact:** structured the 19 external
  `NON_DETERMINISTIC_INSTRUCTION` findings as false positives in the
  [adjudication record](evidence/2026-10-02-non-deterministic-instruction-false-positives/adjudication.json),
  linked to the sealed audit IDs and source spans. This transcribes the existing manual
  review; a separate assistant source-span pass agreed, but is not independent
  domain-expert ground truth and cannot estimate recall.
- **Real repair capture:** one complete provider response was retained at
  `/tmp/crucible-r4-20261002-structure-v1`; offline bundle and raw-capture
  checks pass. The model ended with `finish_reason=length`, so no proposal was
  eligible and no re-audit or behavioral replay ran. This is a retained failed
  outcome, not a completed repair.
- **Repair-loop capture:** after raising the proposal cap from 1,000 to 3,000
  tokens, `/tmp/crucible-r4-20261002-structure-v2` completed with
  `ACCEPTED`. The source finding count moved from 2 to 0, no new findings
  appeared, and the seeded behavioral property that failed on the original
  passed on the repaired variant. All three provider responses had
  `finish_reason=stop`; bundle and raw-capture checks pass. This is one
  synthetic fixture run, not an accuracy or stability estimate.
- **Current next step:** independently reviewed positive and negative cases
  for a held-out evaluation set, with class-specific denominators.

## Selected ideas from the Habr reading

| Idea | Crucible application | Decision |
|---|---|---|
| Record a failure with its source, context, and reproduction before changing a skill ([article 2](https://habr.com/ru/articles/1074184/)) | Keep audit artifacts, corpus/task identities, runtime captures, and dispositions linked | Adopt; this matches the existing sealed-artifact and replay design |
| Classify whether a failure came from the skill, code, local rules, activation, or check ([article 2](https://habr.com/ru/articles/1074184/)) | Adjudicate findings by class and record why a candidate was confirmed, rejected, or left unresolved | Adopt for evaluation; do not turn a single model opinion into a label |
| Require a check to fail before a change and pass after it ([articles 5 and 8](https://habr.com/ru/companies/avito/articles/650073/), [agent mutation pipeline](https://habr.com/ru/articles/1020066/)) | Keep seeded mutations and negative controls; report denominators and abstentions | Adopt; mutation survival is a signal to investigate, not proof of a real defect |
| Inspect the full agent run and turn concrete failures into targeted evaluations ([article 12](https://habr.com/ru/articles/1040756/)) | Preserve complete request/response metadata and compare the same task across variants | Adopt within the capture contract; do not claim agent activation traces when the harness explicitly supplies skill text |
| Put consequential authority in deterministic checks ([prompt injection](https://habr.com/ru/articles/979476/), [testing harness](https://habr.com/ru/articles/1064824/)) | Preserve deterministic audit, recommendation, repair gates, and sealed artifacts | Keep as a core invariant |
| Use a registry to distribute and govern skills ([article 3](https://habr.com/ru/articles/1087464/)) | Relevant to future installation workflows, but does not answer whether methodology is sound | Defer; it does not strengthen the current differentiator |
| Assign weighted quality scores to checks ([article 7](https://habr.com/ru/companies/rostelecom/articles/987244/)) | EVA's weights are author choices and its target domain is structured API tests | Do not import a scalar score; report class-level evidence and uncertainty |

## Sequence and exit evidence

### Days 1–5 — Freeze the evaluation basis

- Pin the exact external corpus revision and record its license and permitted
  demo use before publishing any source-derived material.
- Keep the author's corpus as regression data and reserve independent skills
  for evaluation; do not tune on the same examples used to claim performance.
- Define a small adjudication record: finding ID, class, source span, label
  (`CONFIRMED`, `REJECTED`, or `UNRESOLVED`), rationale, reviewer, and evidence
  reference. Preserve unresolved cases instead of forcing a binary answer.

**Exit:** reproducible corpus identity, provenance/licensing note, and an
explicit labeling rule with positive, negative, and unresolved examples.

### Days 6–12 — Measure the auditor on held-out cases

- Select cases from the external corpus, including negative controls and
  previously observed false-positive patterns.
- Report per-class confusion counts, precision/recall only where both positive
  and negative labels support the denominator, and abstention separately.
- Keep mutation results separate from real-corpus accuracy. A seeded mutant
  tests a known verifier contract; it is not a sample of production defects.
- Resolve only narrow, evidence-backed extraction defects. Keep design
  ambiguities such as configuration imperatives under `Checks` explicitly
  unresolved until the intended oracle contract is decided.

**Exit:** a versioned report with denominators, source identities, negative
controls, false positives, unresolved cases, and no universal-safety claim.

### Days 13–17 — Close the real repair-evidence gate

- Run the existing L7 capture path only when provider credentials are available
  and the operator accepts the provider request/data handling for the fixture.
- Retain the complete bundle, including blocked, rejected, and error outcomes;
  do not retry implicitly or publish raw prompts/responses by default.
- Verify the saved bundle offline and record exactly what a single run does and
  does not establish.

**Current status:** credentials are available. The first retained response
hit the 1,000-token cap and was rejected before re-audit; the cap is now 3,000.
A follow-up capture completed the loop and passed the deterministic re-audit
and seeded behavioral oracle. Preserve both captures, including the failed
first attempt. Treat the accepted run as a single-fixture demonstration only.

**Exit:** one complete, privately retained live L7 evidence bundle that passes
offline verification, or an explicit blocked status with no simulated success.

### Days 18–23 — Make the evidence path easy to inspect

- Build the demo around the single path above, using a corpus revision cleared
  for publication.
- Show scan scope and coverage, source-linked findings, confirmation state,
  repair gate outcome, and export/replay as distinct facts.
- Keep loading, empty, partial, failed, blocked, and completed states visibly
  distinct. Never present partial or empty input as a clean corpus.
- Produce a deterministic local fallback using the existing fixtures; label it
  local so it cannot be confused with the live provider run.

**Exit:** a reviewer can reproduce the local demo, inspect every claim's
evidence, and tell local execution from provider execution.

### Days 24–27 — Integrated release check

- Review ingestion, coverage, finding provenance, model confirmation, repair
  acceptance, replay, and report rendering as one path.
- Reconcile README, technical status, hackathon disclosure, and demo claims with
  retained artifacts; remove stale statements only when their historical scope
  is preserved elsewhere.
- Record known limitations, corpus licensing, and any blocked gate in the
  submission materials.

**Exit:** one coherent build with a reproducible demo and claims bounded by
retained evidence. Stop at the highest fully closed state; do not label an
unfinished gate complete to fill the schedule.

## Explicitly deprioritized

- A new skill registry or signature system: distribution/integrity overlap,
  outside Crucible's current methodology-verification boundary.
- A universal skill-quality score: unsupported by current labels and likely to
  conceal class-specific false positives.
- More mutation operators without hidden expectations and meaningful negative
  controls.
- Public hosting until its data, filesystem, resource, and privacy boundaries
  have their own review.

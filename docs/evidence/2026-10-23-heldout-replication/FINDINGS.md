# Replication across five corpora, two of them held out

**Date:** 2026-10-23  **Branch:** `main`
**Corpora:** five, 2806 skills total. Identities and roles are sealed in
[the corpus seal record](../2026-10-23-heldout-corpus-seal/FINDINGS.md).
**Status:** measurement only. Nothing in the implementation was changed
because of what this record found, so the two `HELDOUT_SEALED` corpora remain
unconsumed.

## Why this record exists

Two findings on 2026-10-23 were based on a single external corpus: that
normative-rule extraction yields almost nothing
([R-01, R-02, R-03](../2026-10-23-rule-extraction-yield/FINDINGS.md)) and that
composition is structurally silent
([C-01, C-02, C-03](../2026-10-23-composition-silent-on-external-corpus/FINDINGS.md)).
One corpus cannot distinguish a property of the analyzer from a property of
that corpus. Three further corpora were added, two of them sealed held-out
before any audit was run.

## Measured

| Corpus | Role | Skills | Rules | Rules/skill | Skills with a rule | MUST+MUST_NOT | Rules with a subject | Checks/skill | Findings | Edges | Abstained | Wall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| author | regression | 101 | 191 | 1.89 | 55 | 99 (52%) | 22 | 2.38 | 108 | **86** | 6 | 480 ms |
| `mukul975` | consumed | 818 | 221 | 0.27 | 143 | 2 (0.9%) | 1 | 2.70 | 1056 | 0 | 6 | 3915 ms |
| `vantaflow` | consumed | 692 | 302 | 0.44 | 302 | 0 (0%) | 0 | 0.86 | 935 | 0 | 6 | 2484 ms |
| `nimadorostkar` | **held out** | 138 | 113 | 0.82 | 82 | 44 (39%) | 0 | 0.34 | 178 | 0 | 6 | 461 ms |
| `TerminalSkills` | **held out** | 1057 | 793 | 0.75 | 467 | 215 (27%) | 4 | 0.68 | 837 | 0 | 6 | 4794 ms |

## What replicated

**R-02 — subject-dependent checks are inert.** Across 2806 skills from five
independent sources, rule `subject` extraction yielded 27 subjects in total,
22 of them in the author's own corpus. `NORMATIVE_CONFLICT` and
`CONDITIONAL_CONTRADICTION` compared zero pairs on every corpus.

**C-03 — composition measures authoring convention.** 86 edges on the author
corpus and **0 on all four independently authored corpora**, including 1057
and 692 skill collections. No independent corpus used either the section
heading convention or a description relation trigger.

**The abstention count is 6 on every corpus.** Six of the eight
precondition-dependent checks abstain universally: `BROKEN_REFERENCE`,
`COMPOSITION_CYCLE`, `CONDITIONAL_CONTRADICTION`, `NORMATIVE_CONFLICT`,
`ORPHAN_SKILL` and `SELF_COMPOSITION`. Across 2806 real skills from five
sources, none of these six has ever fired outside fixtures.

**Cost scaling.** 1057 skills cost 4794 ms against 818 skills at 3915 ms,
consistent with the superlinear auditor curve in
[the cost record](../2026-10-23-cost-scaling/FINDINGS.md).

## What did not replicate, and must be narrowed

**R-01 was too general.** The claim that modal keywords are essentially absent
from independently authored skills was a property of `mukul975`, not of
independent authorship. `TerminalSkills` yields 215 `MUST`/`MUST_NOT` rules
across 1057 skills and a genuinely mixed distribution (`ALWAYS` 264,
`MUST_NOT` 211, `NEVER` 162, `IMPERATIVE` 152, `MUST` 4); `nimadorostkar`
yields 44 across 138. Two `MUST` rules in 818 skills was the outlier, not the
rule.

The narrower claim that survives is about relative yield: the author's own
corpus extracts 1.89 rules per skill, 2.3 times the best independent corpus
(`nimadorostkar`, 0.82) and 7 times the worst (`mukul975`, 0.27). Between 40%
and 82% of skills in every corpus yield no rule at all, the author's corpus
included (46 of 101, 45%).

**Check extraction is not comparable across corpora.** The earlier record
said check extraction performed comparably, which held for the two corpora it
measured (2.38 and 2.70 per skill). Across five it ranges from 0.34
(`nimadorostkar`) to 2.70 (`mukul975`), an eightfold spread.

**The finding-class mix is corpus-dependent.** The earlier "84% from two
pattern classes" was specific to `mukul975`. The top three classes carry
66-88% of findings everywhere, but which classes they are varies: `mukul975`
leads with `COMMAND_ORACLE_WITHOUT_ARTIFACT` (559), `vantaflow` with
`SEMANTIC_REDUNDANCY` (337), and the remaining three with
`REQUIREMENT_WITHOUT_CHECK`.

## New finding — a templated corpus inflates both rules and redundancy

`vantaflow`'s 302 extracted normative rules are **one identical line repeated
302 times**:

```text
- Never say "happy to help", "sure!", "great question", "let me", or s...
```

It appears under a `communication rules — mandatory` heading in 302 of 692
skills, every one of which yields exactly one rule; the other 390 skills
yield none. Distinct rule texts by corpus:

| Corpus | Rules | Distinct texts | Duplicated share | Largest duplicate group |
|---|---|---|---|---|
| author | 191 | 191 | 0% | 1 |
| `mukul975` | 221 | 221 | 0% | 1 |
| `vantaflow` | 302 | **1** | **99%** | **302** |
| `nimadorostkar` | 113 | 113 | 0% | 1 |
| `TerminalSkills` | 793 | 793 | 0% | 1 |

Reproduce the whole table, and the rest of the shape columns, with:

```text
python docs/evidence/2026-10-23-heldout-replication/measure_corpus_shape.py \
  <corpus-root>=<label> ...
```

Two consequences:

- **V-01 — addressed in the evaluation tooling, deliberately not in the
  sealed artifact.** The rule count overstates distinct normative content by
  302 to 1 on this corpus. A reader comparing 302 rules against
  `nimadorostkar`'s 113 would conclude `vantaflow` is nearly three times as
  normative; it declares one obligation.

  On review the audit artifact is not the right place to fix this.
  `preconditions.corpus_inputs.rules` counts rule *records*, which is exactly
  what a precondition question needs; duplication matters when comparing
  corpora, which is an evaluation activity. So the figure lives in
  [`measure_corpus_shape.py`](measure_corpus_shape.py), which reports
  `distinct_rule_texts` and the largest duplicate group beside every count and
  prints an explicit warning when they diverge, rather than in a third audit
  schema bump in one day.
- **V-02 — stated here, then refuted the same day. See
  [the follow-up](../2026-10-23-redundancy-evidence-denominator/FINDINGS.md).**
  The original claim was that `SEMANTIC_REDUNDANCY`'s 337 findings on
  `vantaflow` were candidates driven by shared template text rather than by
  two skills covering the same ground. Measuring the pairs instead of
  reasoning about them reversed it: all 337 follow the name pattern `X` /
  `<prefix>-X`, 43 have byte-identical fingerprints, raw token unions run from
  30 to 116 with a median of 43, and none is trivially small. The corpus
  publishes each skill twice, once bare and once category-prefixed, and the
  check found every instance. This is the check's best demonstrated
  performance on a real corpus, not a false-positive cluster. The original
  claim was an inference from the boilerplate observation; it should have been
  measured before being written down.

## New finding — extraction is keyed to English

`vantaflow`'s most common headings are French: `bonnes pratiques 2026` (420
skills), `garde-fous et anti-patterns` (199), `workflow en étapes` (98).
Heading-driven extraction matches English words -- `composes with`,
`delegates to`, and the verification verbs used for checks -- so a non-English
corpus is partly invisible to it. This is an additional and independent
explanation for low yield that is not about modality vocabulary at all, and it
widens the earlier law: extraction is calibrated not only to the author's
conventions but to English ones.

This is one corpus, and the French headings co-occur with templating, so the
two explanations are not separated here. Separating them needs a non-English
corpus that is not templated.

## Limits of this record

- Five corpora is not a sample of the ecosystem. Four are independent of this
  project; none was randomly sampled, and all five are GitHub-published
  collections, which is itself a selection.
- No finding was adjudicated. Every count is extractor and auditor output.
  `CANDIDATE` means a reason to inspect; 3114 findings across five corpora
  establish nothing about how many are real defects.
- Per-corpus denominators are not pooled: the corpora differ in size by an
  order of magnitude and in convention by more.
- Timings are single runs and carry no authority, per `cost-record/v1`.
- `vantaflow` and `mukul975` are `TUNING_CONSUMED` and cannot support a
  generalization claim. Only `nimadorostkar` and `TerminalSkills` can, and
  this record is the first measurement taken on them.
- Nothing was fixed in response to these results, deliberately. V-01, V-02,
  the English keying and the narrowed R-01 are all live defects whose repair
  would consume a held-out corpus if driven by what was seen here.

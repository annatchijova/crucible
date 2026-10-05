# L16 consolidation: a colliding proposed name silently destroyed an unrelated skill

**Date:** 2026-10-05
**Context:** continuing the LLM-suggestion-layer review (L15's silent-
KEEP-omission gap, found earlier today) into L16 (`consolidation.py`).
This one is a data-destruction bug, not a cosmetic reporting gap.

## The bug

`CONSOLIDATION_SYSTEM_PROMPT` asks the LLM for "a new name... not equal
to any input skill's name" -- but the prompt only ever shows the model
`cluster_skills` (the skills being merged). It is never shown the rest
of the corpus, so it has no way to know whether its chosen name collides
with some OTHER, unrelated skill still in the corpus. `_run_gate_for_
cluster` never checks for this either -- its four acceptance criteria
(redundancy-gone, coverage, novelty, no behavioral gate) say nothing
about name uniqueness. The merge is applied with
`repaired_corpus[proposed_name] = proposed_text`, which silently
overwrites whatever was already stored under that key.

## Reproduced directly

A 3-skill corpus: `retry-a` and `retry-b` (genuinely redundant, real
CONFIRMED `SEMANTIC_REDUNDANCY`), plus `unrelated` (a real, unrelated
skill -- in the test, currency formatting; in the ad hoc repro script,
PDF schema validation). A test-double proposer returns a complete,
coverage-passing merge of `retry-a`/`retry-b`, but names it `unrelated`
(the colliding name).

Before this fix: `run_consolidation` returned `outcome: ACCEPTED`.
Running it through `run_consolidation_batch` (the real workflow) left
`final_skill_names: ['unrelated']` -- the corpus went from 3 skills to
1, and that one remaining entry is the merged retry content, not the
real `unrelated` skill. Its actual methodology (currency formatting /
PDF validation in the two repros) is gone, with no warning, no
rejection, `ACCEPTED` status.

## The fix

A deterministic check right after the proposal is parsed, before any
compile/audit work: if `proposed_name` is not itself a member of the
cluster being replaced (which is fine -- every cluster member is
removed from the corpus by this exact merge, so reusing one of their
names frees it up, not collides) AND `proposed_name` already exists in
the corpus, reject with `NAME_COLLISION`. This is a deterministic gate,
consistent with the project's "LLM never in the decision path" thesis
-- the system prompt's instruction to the model is advisory, not a
safety guarantee, and this bug is exactly what happens when that
distinction is skipped for one specific check.

2 new tests: the collision case (rejects, does not destroy the
unrelated skill), and a negative control proving a proposed name equal
to one of the cluster's OWN members is still correctly accepted (not
a false collision). Full suite and mutation gate green.

## Severity note

Unlike every other finding from this session's L2-check sweep (false
positives in a CANDIDATE-status audit check, caught by the LLM
confirmation layer or a human before anything changes), this one is in
the deterministic *write path* of a workflow that mutates the corpus on
disk. A false positive wastes attention; this bug destroys real
content. Found by reviewing the acceptance-gate logic directly (not by
a held-out corpus run), the same way the L15 gap was found -- reading
the code that decides what happens next, not just measuring what a
pattern-matcher flags.

# L15 recommendation core: a clean skill had no entry at all, not even KEEP

**Date:** 2026-10-05
**Context:** moving from "polish the deterministic scan" (L2, this
session's earlier work) to "how the LLM layer suggests/groups" per
Anna's framing. First stop: `recommendation.py` (L15), the
deterministic core that decides each skill's KEEP/NEEDS_CONFIRMATION/
MODIFY/DELETE bucket before any narration happens.

## The bug

`compute_recommendations` builds its per-skill `by_skill` map by
iterating `audit["findings"]` -- the only skill names it can ever see
are the ones that appear in at least one finding. A skill with zero
findings (a genuinely clean skill, or one where every CANDIDATE finding
was REJECTED on confirmation) never gets a key in `by_skill` at all, so
it never gets a recommendation entry -- not even KEEP.

This propagates all the way to the rendered report. `build_final_report`
sets `report["skill_count"] = len(ir["skills"])` (the true corpus size)
but only ever populates `report["skills"]` from
`recommendations["skills"].items()`. Reproduced directly: a one-skill
corpus with a deliberately trivial, defect-free `SKILL.md` produced
`skill_count: 1`, `summary.total_skills: 0`, `skills: {}`. The rendered
Markdown/HTML/PDF header states "Skills scanned: 1" while the body lists
zero skill sections -- a visible, misleading gap a reader would
reasonably read as "something went wrong" or "a skill is being hidden,"
not "this skill is clean."

**The existing test for this exact behavior had the bug baked in as the
spec**: `test_skill_with_no_findings_is_kept` asserted
`result["skills"] == {}` -- its own name claims the skill is kept, its
body proves it has no representation whatsoever. Not a new regression;
present since this module was written.

## The fix

`compute_recommendations` gained an optional `all_skill_names` parameter
(the full corpus skill-name list, from `ir["skills"]`); any name in that
list not already covered by a finding gets `by_skill.setdefault(name, [])`
before the recommendation loop, so it resolves to an explicit KEEP with
`total_finding_count: 0`. Kept optional and defaulting to the old
behavior, since the existing unit tests build a bare `audit` dict with
no real compiled corpus to draw names from -- changing the default
would have broken every one of them for no reason; only `final_report.py`
(the one real caller with an actual `ir`) passes it.

`build_final_report` now passes `[s["identity"]["name"] for s in
ir["skills"]]`. `narrate_skill`'s existing KEEP branch already never
calls the model (confirmed by reading it, not assumed) -- the fix adds
zero LLM/network cost for clean skills, it only makes them visible in
the deterministic layer.

Renamed the misleadingly-passing test to state what it actually proves
(the limitation, not the fix) and added two new tests: one proving a
clean skill gets an explicit KEEP when `all_skill_names` is given, and
one at the `build_final_report` level proving `skill_count ==
summary.total_skills == len(skills)` end to end, with a real clean skill
in the mix. Full suite and mutation gate green.

## Why this matters for "pulir cómo sugiere la capa LLM"

This isn't an LLM-prompt-quality issue -- it's upstream of the LLM
entirely, in the deterministic bucketing the narrator trusts verbatim.
But it directly affects what a user reading the final report sees: a
corpus report that silently omits every clean skill undersells exactly
the skills a methodology audit should be *reassuring* about, not just
flagging the bad ones. Worth keeping in mind for the next pass
(consolidation.py / L16's clustering and merge-proposal logic): check
whether a similar "only skills that show up in some evidence get an
entry" gap exists there too.

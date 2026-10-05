# SEMANTIC_REDUNDANCY audit, and the 13 zero-hit checks

**Date:** 2026-10-05
**Context:** closing out the systematic L2-check held-out audit
(Anna's "pulir que nuestro escanear haga las cosas de manera
coherente"). Last two items: `SEMANTIC_REDUNDANCY` (2 held-out hits,
deliberately deferred earlier) and the 13 checks with zero held-out
hits.

## SEMANTIC_REDUNDANCY: a genuine false-positive mechanism found, but the obvious fix breaks the one already-confirmed true positive

Read both held-out pairs in full, same method as the mukul975
confirmation earlier this session (hand-computed Jaccard, read actual
content, not just the finding's truncated evidence string).

- `microsoft-skills/azure-cosmos-py` vs `azure-cosmos-rust`: 15/22
  tokens (68%) overlap on `description + rules + checks`. Both skills
  have **zero rules and zero checks** -- the comparison is, in
  practice, comparing descriptions only. The 15 shared tokens are
  almost entirely domain nouns (`cosmos`, `azure`, `db`, `container`,
  `document`, `nosql`, `partition`, `cosmosclient`) that any Cosmos DB
  skill in any language would use; the only non-shared tokens are
  `python`/`sdk` vs `rust`/`library`. This is the same Azure service
  ported across two languages, described with the same template.
- `sports-skills/mlb-data` vs `nhl-data`: 66/97 tokens (68%) overlap,
  same zero-rules/zero-checks situation. The intersection is mostly a
  **shared "related skills" list** both reference verbatim (`nba-data`,
  `nfl-data`, `cricket-data`, `football-data`, `golf-data`, `wnba-data`,
  `cbb-data`, `cfb-data`, `tennis-data`, `kalshi`, `polymarket`,
  `sports-news`...) -- an artifact of being siblings in the same data-
  skill suite, not evidence the two skills' own content overlaps.
  The genuinely sport-specific vocabulary (`pitch`/`velocity`/`splits`/
  `minor league` for MLB; `hockey`/`ahl`/`khl`/`on-ice`/`shot`/
  `skater-goalie` for NHL) is real and non-overlapping.

Both pairs' real differentiating content lives in `procedural_steps`
(16 vs 10 steps for the Cosmos pair; 15 vs 13 for the sports pair),
which `_check_semantic_redundancy` never includes in its Jaccard
calculation -- only `description + rules + checks`. Measured directly:
including `procedural_steps` drops azure-cosmos-py/rust's overlap from
68% to **17%**, and mlb-data/nhl-data's from 68% to **59%** (both fall
below the 2/3 threshold, correctly un-flagging both).

**But this is not a safe fix**: the same change applied to mukul975's
one already-confirmed true positive (`hardening-linux-endpoint-with-
cis-benchmark` vs `hardening-windows-endpoint-with-cis-benchmark`,
hand-verified earlier this session as genuinely redundant CIS-benchmark
templates) ALSO drops its overlap below threshold -- from 69% to
**33%**. Procedural steps are full of generic verb/benchmark vocabulary
that dilutes the Jaccard ratio broadly, not selectively; including them
doesn't cleanly separate true from false positives here, it just
lowers sensitivity across the board, trading the false positives found
on held-out for a false negative on the one confirmed real case.

**Not fixed.** This is a genuine design trade-off -- a different
weighting (steps counted but discounted, a lower threshold applied
only when rules+checks are both empty, or a per-source-field
comparison instead of one pooled bag of tokens) might resolve it, but
inventing one without more evidence would be exactly the "ad hoc
word-list patch to a design problem" this session has consistently
avoided. Recorded as an open question for Anna, same discipline as
`UNPINNED_DEPENDENCY`/`CLAIM_WITHOUT_PROVENANCE`.

## The 13 zero-hit checks: not independently re-tested, and here's why that's a reasoned choice, not a skip

`broken_references`, `self_composition`, `composition_cycles`,
`orphan_skills`, `structural_redundancy`, `normative_conflict`,
`conditional_contradiction`, `llm_in_decision_path` (only its negative/
positive polarity tests fired this session; no genuine positive found
on held-out), `silent_failure`, `hardcoded_credential`,
`missing_timeout`, `floating_point_in_decision_path`,
`overgeneralization` all produced zero findings on the three held-out
corpora.

Did not construct new synthetic probes for each one. Reasoning: every
one of these 13 already has falsifiable positive-fixture tests in the
existing suite (confirmed passing in every full-suite run this
session, 800+ tests), which already proves each check *can* fire
given matching input -- ruling out "structurally broken, can never
fire" as an explanation for the zero count. A true zero on three
curated, modern, mostly well-written corpora (official SDK skills,
an enterprise sports-data suite, a large curated general collection)
is plausible on its own terms for several of these classes
specifically: `composition_cycles`/`self_composition`/
`orphan_skills`/`structural_redundancy` need multi-skill composition
structure that a flat, independently-authored skill collection rarely
has; `hardcoded_credential`/`missing_timeout`/`floating_point_in_
decision_path` are narrow, specific engineering defects that a
competent author simply may not make.

**Not concluded as "well-calibrated"** -- that would need the same
hand-verification rigor every other finding in this session got, and
zero hits means there is nothing to hand-verify. Recorded honestly as
unassessed: a corpus that happens to trigger even one of these would
be the next real test of these 13 checks' calibration, not this one.

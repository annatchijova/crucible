# Families of mergeable skills: none larger than five in the measured corpora

**Date:** 2026-10-28
**Question:** the product goal includes "if ten skills can become one, say so".
Consolidation already merges a connected group of any size
([L16](../2026-10-24-l16-live-real-corpus/FINDINGS.md)), and the narrated report
now presents a group as "N skills into 1". Do real corpora contain such
families under any lexical similarity object, or only under the whole-skill
fingerprint already known to stop at pairs?
**Script:** [`measure_families.py`](measure_families.py). It is exact and
deterministic, and no model is involved.

## Result

| Similarity object | `vantaflow` (692) largest family | `mukul975` (818) largest family |
|---|---|---|
| whole-skill fingerprint, Jaccard 2/3 (shipped) | 2 | 2 |
| description only, Jaccard 2/3 | 2 | 2 |
| description only, Jaccard 1/2 | 2 | 2 |
| description only, Jaccard 2/5 | 4 | 2 |
| containment of a smaller skill in a larger one, 4/5 | 2 | 2 |
| containment, 2/3 | 5 (one hub with four contained) | 2 |

`vantaflow`'s families are its republication pairs (each skill bare and
category-prefixed), occasionally joined by one related topic. `mukul975` has
818 skills on overlapping security topics, and no two of them pass any of these
bars except a handful of near-twins (Linux/Windows CIS hardening, two
Kerberoasting skills).

## Interpretation

- **Negative, and registrable:** in these two corpora, a family of ten
  mergeable skills does not exist under any of the lexical objects tried, and
  lowering the threshold to 2/5 does not produce one. The "N into 1" path is
  implemented and tested on a synthetic group of three, but it is unexercised
  above five on real input.
- Families of skills on the same topic, such as the many `performing-*`
  security procedures in `mukul975`, are lexically distinct methodologies, not
  near-copies. Whether some of them *should* be one skill is a judgement about
  decision and scope (L5 in the agenda), and no lexical bar measured here
  makes it.
- No detector was added on the strength of this. A scope-overlap or
  containment check would be a new claim needing its own evidence, and on this
  data it would mostly re-find the pairs already found.

## Limits

- Two corpora, both previously consumed. The held-out corpora were not run.
- Lexical objects only. A model judging "same decision, same scope" could find
  families these bars miss, but by contract it could only nominate them; it
  could not decide.

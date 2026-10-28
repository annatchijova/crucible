# Crucible Skill Quality Report

- **Report digest:** `sha256:dd78387089b1edac6ddba8a357b04ddcb6af5a927344b6605b72364b1d06e493`
- **Audit digest:** `sha256:60662c6958ed66e9026fe6e465593b514353e02081600ddf22868a851209d47a`
- **Confirmation digest:** `sha256:944d96cf86b13e5e05721abd0292757b4e9b3bb443825dbd92bcb9036dfddc0e`
- **Input:** a skill directory
- **Skills scanned:** 4
- **Recommendations:** KEEP: 4

## Summary

Mock narration.

## Duplicate skills to consolidate

Each group is a set of skills joined by confirmed redundancy pairs. The recommendation is to merge each group into one skill; which member survives, and what the merged text says, is not decided here. Add --with-consolidation to have a merge proposed for each group and checked by the deterministic gate.

No confirmed duplicate group in this corpus.

## Contradictions between rules

Not evaluated: the contradiction checks abstained because no two extracted rules share a normalized subject, so this check compared no rule pair. Read this with rules_with_subject: only the RFC-2119 modal extraction route assigns a subject at all, while the negative-starter and imperative routes record an empty one by construction (no object extraction), so a low count usually means a subject was never attempted rather than attempted and unmatched. This is not evidence that the skills agree with each other.

## Rule text repeated across skills

The same rule text appears verbatim in several skills. A repeated block is a candidate for one shared skill or reference document; it is not by itself a defect, and editing one copy leaves the others behind.

No rule text is repeated verbatim across skills.

## Suggested rewrites

0 of 0 skill(s) recommended MODIFY received a suggested rewrite; 0 passed the deterministic gate. The gate re-audits text only, so an accepted rewrite is one the auditor no longer objects to, not evidence of better agent behaviour.

No skill recommended MODIFY has a finding this path can rewrite.

## What was not analyzed

An ABSTAINED check produced no findings because this corpus did not supply the input it consumes; that is not evidence the corpus is free of that defect class.

- **BROKEN_REFERENCE abstained**
  - requires declared_relations, observed 0: the corpus declares no composes_with or delegates_to relation, so this check had no relation to examine
- **COMPOSITION_CYCLE abstained**
  - requires declared_relations, observed 0: the corpus declares no composes_with or delegates_to relation, so this check had no relation to examine
- **CONDITIONAL_CONTRADICTION abstained**
  - requires comparable_rule_pairs_by_subject, observed 0: no two extracted rules share a normalized subject, so this check compared no rule pair. Read this with rules_with_subject: only the RFC-2119 modal extraction route assigns a subject at all, while the negative-starter and imperative routes record an empty one by construction (no object extraction), so a low count usually means a subject was never attempted rather than attempted and unmatched
- **NORMATIVE_CONFLICT abstained**
  - requires comparable_rule_pairs_by_subject, observed 0: no two extracted rules share a normalized subject, so this check compared no rule pair. Read this with rules_with_subject: only the RFC-2119 modal extraction route assigns a subject at all, while the negative-starter and imperative routes record an empty one by construction (no object extraction), so a low count usually means a subject was never attempted rather than attempted and unmatched
- **ORPHAN_SKILL abstained**
  - requires declared_relations, observed 0: the corpus declares no composes_with or delegates_to relation, so this check had no relation to examine
- **SELF_COMPOSITION abstained**
  - requires declared_relations, observed 0: the corpus declares no composes_with or delegates_to relation, so this check had no relation to examine

## Skills

### adonisjs -- KEEP

No action recommended: 1 candidate finding(s) were raised and all were rejected by confirmation.

| Finding | Status | Class | Evidence |
|---|---|---|---|
| finding-0001 | REJECTED | REQUIREMENT_WITHOUT_CHECK | skill has 1 normative rule(s) but 0 extracted checks |

### auth-system-setup -- KEEP

No action recommended: 1 candidate finding(s) were raised and all were rejected by confirmation.

| Finding | Status | Class | Evidence |
|---|---|---|---|
| finding-0002 | REJECTED | REQUIREMENT_WITHOUT_CHECK | skill has 1 normative rule(s) but 0 extracted checks |

### aws-rds -- KEEP

No action recommended: 1 candidate finding(s) were raised and all were rejected by confirmation.

| Finding | Status | Class | Evidence |
|---|---|---|---|
| finding-0003 | REJECTED | REQUIREMENT_WITHOUT_CHECK | skill has 1 normative rule(s) but 0 extracted checks |

### batch-processor -- KEEP

No action recommended: 1 candidate finding(s) were raised and all were rejected by confirmation.

| Finding | Status | Class | Evidence |
|---|---|---|---|
| finding-0004 | REJECTED | REQUIREMENT_WITHOUT_CHECK | skill has 1 normative rule(s) but 0 extracted checks |

## Methodology

The recommendation for every skill (KEEP, NEEDS_CONFIRMATION, MODIFY, or CONSOLIDATE) is computed by a deterministic rule over L2 audit findings and L2.5/L12 confirmation verdicts, before any language model is consulted. The model is given that decision as a fixed fact and asked only to explain it in prose, citing findings by id. Every finding id the model cites is checked after the fact against the sealed findings for that skill; an id that does not exist there is listed as an untraceable claim, not silently presented as evidence. report_digest is the canonical seal of this report: recompute it independently to confirm this rendering was not altered after the fact.

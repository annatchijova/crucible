# Polarity-blindness sweep: variant analysis across all rules-scanning checks

**Date:** 2026-10-04
**Context:** polarity blindness (a check scans `rules` for an
action-describing pattern without ever consulting the rule's own
`modality`, so a `MUST_NOT`/`SHOULD_NOT`/`NEVER` rule *prohibiting* the
risky action gets flagged as if it *instructed* it) turned out to be
the single most-repeated mechanism found this session -- 5 separate
checks had it, found one at a time via held-out corpus hits
(NON_DETERMINISTIC_INSTRUCTION, IRREVERSIBLE_WITHOUT_REVIEW [parallel
session], UNBOUNDED_RETRY, UNVALIDATED_EXTERNAL_INPUT,
SECRET_IN_OUTPUT). Per Anna's direction ("sí" to a proactive sweep),
checked every remaining check that scans `rules` for whether its
trigger vocabulary plausibly overlaps with an action a `NEVER`/
`MUST_NOT` rule could legitimately prohibit, rather than waiting for a
6th/7th/8th/9th corpus to reveal each one.

## Checks hardened (4), all missing the guard entirely before this

- **HARDCODED_CREDENTIAL**: `_SECURE_CREDENTIAL_PATTERNS` already had an
  adjacency-only `\bnever\s+hardcode\b`/`\bdo\s+not\s+hardcode\b` guard
  -- the same shape that already broke for SECRET_IN_OUTPUT on a
  comma-separated list, and `_HARDCODED_CREDENTIAL_PATTERNS`'s own
  pattern 2 ("put/set/store/write/place ... secret ... directly") has
  no adjacency guard at all. A rule like "Do not put a secret directly
  in the script" was never protected.
- **SILENT_FAILURE**: "Never silently swallow an exception" matches
  `_SILENT_FAILURE_PATTERNS`'s `\bswallow\s+(?:the\s+)?exception\b`
  with no polarity check at all.
- **LLM_IN_DECISION_PATH**: "Never let the model decide the final
  verdict" matches `_LLM_DECISION_PATTERNS`'s `\blet\s+(?:the\s+)?
  (?:model|LLM|AI)\b` with no polarity check -- notably, this check's
  entire subject matter (keeping the LLM out of the decision path) is
  exactly the kind of invariant a methodology would state as a
  prohibition.
- **FLOATING_POINT_IN_DECISION_PATH**: "Never use float for the money
  calculation" matches `_FLOAT_DECISION_PATTERNS` with no polarity
  check.

Fix: the same `_NEGATIVE_MODALITIES` guard already proven 5 times,
reused as-is (6th-9th instances). 8 new regression tests (a positive/
negative modality pair per check).

## Not touched, and why

Checked every other `rules`-scanning check for the same shape and
judged it not clearly applicable:

- `UNPINNED_DEPENDENCY`, `MISSING_TIMEOUT`, `COMMAND_ORACLE_WITHOUT_
  ARTIFACT`, `CLAIM_WITHOUT_PROVENANCE`, `OVERGENERALIZATION`,
  `NORMATIVE_CONFLICT`: different shape -- absence-detection, claim-
  text-shape, or multi-rule conflict, not "detect an instruction to DO
  risky action X," so a `NEVER` rule's own text doesn't plausibly
  contain the trigger vocabulary the same way.
- Preemptive hardening with no real triggering instance found in any
  of the 5 available corpora (held-out x3, mukul975, author's own) --
  this is the first time this session a fix was made without a
  concrete found false positive. Verified by diffing skill+rule-id
  sets before/after on all 5 corpora: **0 removed, 0 added,
  everywhere** (the author's corpus keeps its 2 genuine
  LLM_IN_DECISION_PATH positive-modality hits, unaffected). This
  confirms the fix is safe (introduces no regression) but its direct
  real-world payoff is speculative until a corpus with this exact
  phrasing shows up -- recorded honestly as hardening against a
  demonstrated *class* of bug, not a demonstrated instance in these 4
  checks specifically.

Full suite and mutation gate green.

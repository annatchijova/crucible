# SECRET_IN_OUTPUT and UNBOUNDED_RESOURCE audit

**Date:** 2026-10-04
**Context:** continuation of the systematic L2-check held-out audit,
finishing the checks with any held-out hits (SECRET_IN_OUTPUT 2,
UNBOUNDED_RESOURCE 3).

## SECRET_IN_OUTPUT (2 hits)

### Fixed: polarity blindness, comma-list variant (1/2) — 5th instance this session

`terminalskills/routerbase-gateway` rule-0001, modality `NEVER`:
"Never paste, print, log, or commit a real API key." The existing
`_SECRET_PROTECTION_PATTERNS` already has `\bnever\s+(?:log|print|
output|echo)\b` -- the author of that pattern clearly anticipated this
exact shape -- but it requires "never" immediately adjacent to the
verb. A comma-separated list of banned actions ("paste, print, log, or
commit") puts "paste" between them, breaking the adjacency. Fixed the
same way the 4 prior instances were: reused the rule-level
`_NEGATIVE_MODALITIES` guard instead of trying to patch the list-
handling in the protection pattern.

### Deferred: documentation-authoring meta-reference (1/2), a step with no modality to check

`microsoft-skills/skill-creator` step-0097: "Show `DefaultAzureCredential`
in the primary auth example. **Do not delete API-key examples**..." --
this is a skill *about how to author other Azure SDK skills*,
discussing API-key code *examples* as a documentation topic, not
instructing the agent to print/log an actual secret value. It's a
procedural step (no `modality` field to check), and the match comes
from "Show" + (long gap) + "API-key" -- a genuine descriptive-vs-
prescriptive case, same open-question family as NON_DETERMINISTIC_
INSTRUCTION's deferred mechanisms. Not fixed.

## UNBOUNDED_RESOURCE (3 hits)

### Fixed: negation directly in front of the unbounded-action phrase (1/3)

`terminalskills/i18next` step-0001: "Split translations into
namespaces by feature — **don't load everything**." The trigger
pattern `\bload\s+everything\b` matched the literal substring inside
"don't load everything," ignoring the negation immediately in front of
it -- this instruction is explicitly telling the agent to AVOID the
unbounded action, the opposite of what it was flagged for. Added a new
bound pattern recognizing `(?:don't|do not|never|avoid)
(?:load|read|collect|gather|fetch|buffer|caching) (?:all|everything|
the entire)` -- the same negation-adjacency idiom
`_SECRET_PROTECTION_PATTERNS` already uses for "never log"/"do not
print".

### Deferred: domain-specific sense of "read all" (2/3)

- `appwrite` step-0006: "Set permissions so users can only edit their
  own recipes but **read all** published ones." -- "read all" here
  means "has read access to every published record" (an authorization
  *scope*), not "load every record into memory at once" (a resource-
  bounding concern). A pure word-collision false positive, same class
  as several other checks' deferred mechanisms this session
  (NON_DETERMINISTIC_INSTRUCTION's "Random Forest", UNBOUNDED_RETRY's
  "REPEAT" methodology step name).
- `markdown-writer` step-0001: "Read all route files to identify
  endpoints." -- plausibly a genuine true positive (no bound stated);
  left untouched.

Not fixed. Narrowing or generalizing "read all" risks the same kind of
over-broadening already avoided elsewhere this session.

## Verified by diffing skill+rule-id sets

| Check | Corpus | Before | After | Removed | Added |
|---|---|---|---|---|---|
| SECRET_IN_OUTPUT | terminalskills | 1 | 0 | 1 | 0 |
| SECRET_IN_OUTPUT | microsoft/sports/mukul975/author | unchanged | unchanged | 0 | 0 |
| UNBOUNDED_RESOURCE | terminalskills | 3 | 2 | 1 | 0 |
| UNBOUNDED_RESOURCE | microsoft/sports/mukul975/author | unchanged | unchanged | 0 | 0 |

4 new tests (positive/negative pairs for both fixes). Full suite and
mutation gate green.

## SEMANTIC_REDUNDANCY (2 hits) — not investigated this round

`azure-cosmos-py`/`azure-cosmos-rust` (same Azure service, different
language SDKs) and `mlb-data`/`nhl-data` (different sports, same
authoring template) both exceeded the 2/3 Jaccard threshold. Not read
in full this round -- this check was already confirmed well-calibrated
against mukul975 earlier in this session
(`docs/evidence/2026-10-02-mukul975-corpus-audit/FINDINGS.md`), and
these 2 held-out hits are a small enough sample that a real
investigation (hand-computing overlap, same method as that earlier
confirmation) is worth doing as its own pass rather than a rushed
read here. Flagged as remaining work, not concluded either way.

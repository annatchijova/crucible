# Held-out adjudication of REQUIREMENT_WITHOUT_CHECK, CHECK_WITHOUT_ORACLE, MISSING_FAILURE_MODE, SCOPE_TRIGGER_MISMATCH

**Date:** 2026-10-04
**Corpus:** the same three held-out repositories pinned in
`docs/evidence/2026-10-04-held-out-corpora-adjudication/FINDINGS.md`
(microsoft/skills @ `ce7edea9`, machina-sports/sports-skills @ `c5a487da`,
TerminalSkills/skills @ `a021875c`, same 400-entry TerminalSkills sample
manifest reused). Cloned directly to `~/crucible-corpora/held-out-*` and
compiled per-repo with `compile_corpus` (not through the
`--scan-installed-collection` symlink/budget path the other session
used) -- `IRREVERSIBLE_WITHOUT_REVIEW` reproduced that session's exact
published count (47) on this reconstruction, which is taken as
confirmation the corpora match closely enough for this adjudication.

| Class | microsoft-skills (61) | sports-skills (27) | terminalskills (399/400) | Total |
|---|---|---|---|---|
| REQUIREMENT_WITHOUT_CHECK | 5 | 4 | 109 | 118 |
| CHECK_WITHOUT_ORACLE | 4 | 4 | 14 | 22 |
| MISSING_FAILURE_MODE | 1 | 0 | 40 | 41 |
| SCOPE_TRIGGER_MISMATCH | 1 | 0 | 14 | 15 |

## REQUIREMENT_WITHOUT_CHECK: overwhelmingly a genuine true-positive class here

Sampled 15 of 118 at random, read in full. TerminalSkills uses a
template entirely different from mukul975's (Overview -> Workflow/Steps
-> Examples -> Guidelines), with **no equivalent of a Checks/
Verification/Validation section at all**. Confirmed by reading
`preact`'s `## Guidelines` end to end: five caveats/gotchas sentences,
zero checkable claims. 10/10 TerminalSkills samples showed this same
shape. This is reassuring evidence that the mukul975 "Validation
Criteria" false-positive mechanism does not generalize -- a differently-
templated corpus produces a check that is, overwhelmingly, correct.

One new, narrow, deferred observation from `sports-skills/xctf-data`: an
`## Error Handling` section phrases its verification instructions after
a colon-delimited clause, not as the sentence's first word --
`1. For \`get_athlete_profile\`: confirm \`athlete_id\`... matches the
TFRRS URL exactly` -- so `_VERIFICATION_STARTER` (which only matches a
verb as literally the first word of the line) never sees "confirm" here.
A real, small extraction gap, not investigated further this round; noted
for a future pass if it recurs.

## CHECK_WITHOUT_ORACLE: a second, pre-existing false-positive mechanism found, distinct from and predating the mukul975 "Validation Criteria" one

Read all 22 in full. Two different mechanisms, neither one the same as
mukul975's:

### Mechanism E (new): section-title substring collision

`_extract_checks`'s section filter is `if not any(k in title for k in
("check", "verification", "validation")): continue` -- a bare substring
test, not a match against the section being *about* checks. A heading
that merely *contains* one of those words as part of a longer, unrelated
phrase triggers extraction of the section's entire content as checks:

- `kalshi`, `### Futures Market Check` (a procedural step about checking
  futures markets, not a checklist) -> "Present top contenders with
  probability and volume." extracted as a check, correctly flagged
  `CHECK_WITHOUT_ORACLE` since it is a presentation instruction, not a
  verifiable claim at all -- the real defect is the extraction, not the
  oracle classification.
- `terminalskills/web-research`, `### Example 3: Fact-checking and
  verification` -> three literal search-query strings
  ("microservices deployment frequency study") extracted as checks.
- `terminalskills/microsoft-teams`, `### Example 2: Build a slash-
  command bot for system health checks` -> "Fetch current metrics from
  the monitoring API endpoints" (a setup step) extracted as a check.
- `polymarket`/`sports-news`/`tennis-data`: same shape as `kalshi` --
  presentation/formatting instructions under a heading that happens to
  contain "check"-family vocabulary.

This is a **pre-existing bug**, not introduced by this session's
"validation" addition -- the substring test on "check"/"verification"
was already this loose before any fix landed. It did not surface clearly
on mukul975 because that corpus's non-Checks headings rarely happen to
contain those words as incidental substrings; this held-out corpus's
differently-styled headings ("Futures Market Check", "...system health
checks", "Fact-checking and verification") hit it constantly. A rough
corpus-wide scan found **128 headings** across the three held-out
repositories that contain "check"/"checks"/"verification"/"validation"
as a substring of a longer title, not as the section's actual subject.

### Mechanism A (confirmed to generalize): the mukul975 "Validation Criteria bare bullet" pattern

`dns-record-analyzer`'s real `## Validation Criteria`-equivalent section
reproduces the exact mukul975 shape: "MX records exist and resolve to
valid hostnames", "Priority values are reasonable" -- bare declarative
outcome statements, zero verification marker. Confirms this mechanism
(flagged as an open design question in
`docs/evidence/2026-10-02-requirement-without-check-audit/FINDINGS.md`'s
2026-10-04 addendum) is real and not mukul975-specific.

`terminalskills/regression-tester`'s 4 findings are a third shape worth
naming separately: "Identify untested code paths...", "Uncovered
branches...", "Edge cases..." -- these are TASK/PROCEDURE items (what to
look for), extracted from a section that evidently matched the title
filter, misclassified as checks rather than steps. Not yet traced to a
specific heading; flagged, not resolved this round.

## MISSING_FAILURE_MODE: genuine true positives, same template pattern

33 hits (count dropped from an earlier 41 after the parallel session's
`a522fce` landed -- re-measured at current HEAD). Sampled 5 at random
(`jupyter`, `poetry`, `neon`, `whisper`, `growth-hacking`): zero
occurrences anywhere in the body of any failure-mode vocabulary (base
or conjugated forms). Same TerminalSkills template as REQUIREMENT_
WITHOUT_CHECK's finding -- `## Guidelines` sections are caveats/gotchas,
but phrased without any of the check's vocabulary, and the heading
itself ("Guidelines") is too generic to safely add as a signal (unlike
"Pitfalls"/"Troubleshooting", it doesn't specifically denote failure
content). Correctly CANDIDATE; not a false-positive mechanism.

## SCOPE_TRIGGER_MISMATCH: genuine instances of the already-accepted lexical-vs-semantic limitation

15 hits. Read 3 in full (`referral-program`, `great-expectations`,
`d3`): each is a real, on-topic skill whose one extracted rule happens
to use completely different vocabulary than its trigger --
`great-expectations`'s trigger is about dataset validation/expectations,
its only rule is "Never put a database password directly in a
connection string" (a security rule incidentally present in a data-
validation skill). Same shape as the already-accepted residual in
`docs/evidence/2026-10-02-scope-trigger-mismatch-audit/FINDINGS.md`. Not
a new mechanism; the check's own stated limitation holding up as
expected.

## Cross-reference: independent convergence with a parallel session

While this adjudication was in progress, a separate, concurrently-running
session (paused by Anna shortly after) independently found and fixed two
of the same issues reported above, against the same held-out corpus,
citing the same example skills (`polymarket`, `web-research`,
`microsoft-teams`):

- The numbered-list-under-a-real-Checks-heading gap (mechanism A's
  `implementing-next-generation-firewall-with-palo-alto` residual from
  `docs/evidence/2026-10-02-requirement-without-check-audit/FINDINGS.md`)
  -- fixed in commit `a522fce`.
- The section-title substring-collision mechanism (mechanism E above) --
  found, NOT fixed (same "shape-aware match is a larger, riskier change"
  reasoning this document also reaches independently).

Both sessions reading the same real examples and reaching the same
conclusions independently is treated as corroboration, not as one
session's work superseding the other's.

## Update, same date: mechanism E fixed

Investigated the "shape-aware match is riskier" concern both sessions
raised, and found the actual safe boundary: the false cases
(`web-research`'s "Example 3: Fact-checking and verification",
`microsoft-teams`'s "Example 2: ...system health checks") are all
`### Example N: ...` sub-headings under a top-level `## Examples`
section -- narrative usage walkthroughs, a role `## Examples` already
has everywhere else in this compiler, not a checklist. The genuine
cases (`kalshi`'s "Futures Market Check", `polymarket`'s "Live Odds
Check") are real, non-Example, 3-step verification procedures with the
same "N-word phrase ending in Check" shape -- title shape alone cannot
tell them apart, but the `Example N:` prefix can, cleanly. A corpus-wide
scan found dozens of `Example N:` headings containing check vocabulary
across the held-out TerminalSkills repo alone, not just the 2 originally
sampled.

Fix: `_EXAMPLE_HEADING` (`^example\s*\d*\b`) excludes any such heading
from `_extract_checks`'s Checks/Verification/Validation section match.
2 new compiler-level tests (the exclusion, and a negative control
proving "Futures Market Check" -- same shape, no "Example" prefix --
still matches). Verified by diffing, not just counting:

| Corpus | CHECK_WITHOUT_ORACLE before -> after | REQUIREMENT_WITHOUT_CHECK before -> after |
|---|---|---|
| terminalskills | 14 -> 8 | 109 -> 110 |
| mukul975 | 326 -> 326 (0 removed, 0 added) | 23 -> 23 |
| Author's own corpus | 7 -> 7 | 21 -> 21 |

Zero effect on mukul975/author (neither corpus has a real, content-
bearing `## Example N:` section matching this pattern -- the `Example:
Validate MS17-010...`-style lines found earlier in mukul975 were shell
comments inside code fences, already excluded from `sections` entirely,
not real headings this fix could touch). `REQUIREMENT_WITHOUT_CHECK`
rose by 1 on terminalskills -- the same "noise down, signal up" pattern
the parallel session's own fixes produced: a skill that looked like it
had checks (via the now-excluded Example-section extraction) correctly
surfaces as lacking them. Full suite and mutation gate green.

## Update, same date: METHODOLOGICAL_VACUITY audited, and a much larger root cause found and fixed

Anna's own framing for continuing this work: "pulir que nuestro escanear
haga las cosas de manera coherente." Audited `METHODOLOGICAL_VACUITY`
(16 hits on the held-out corpus, previously unaudited) next, by held-out
hit volume.

All 16 were `terminalskills` skills with exactly the same shape: 1
normative rule, 0 procedural steps, 0 checks. Read `preact` in full:
it has a genuine `## Instructions` section (already in
`_PROCEDURAL_SECTIONS`) with real procedural content -- but structured
as narrative prose and code blocks under topic-named sub-headings
(`### Install`, `### Components and Hooks`, `### Signals`), never
numbered, never bulleted. `_extract_procedural_steps`'s existing
nested-sub-heading pass (added for `### 1. Scaffold the endpoint`-style
numbered sub-headings, see the entry above) required a leading number,
so none of this matched. Checked all 16: 15 share the exact
`## Instructions` -> `### <Topic>` shape (`vllm`, `solid-js`,
`nanostores`, `goose`, `great-expectations`, `libsql`, `magicui`,
`nativewind`, `paperclip`, `rive`, `segment`, `supermemory`,
`terminal-skills`, `adonisjs`, `vertex-ai-gemini` with an equivalent
non-"Instructions" variant) -- one dominant, corpus-wide authoring
convention for general-purpose dev-tool skills, not 16 separate issues.

This is larger in scope than the numbered-sub-heading fix it builds on:
it also plausibly explains a meaningful share of `REQUIREMENT_WITHOUT_
CHECK` (110) and `MISSING_FAILURE_MODE` (33-41) on the same corpus,
since a skill whose only real content lives in topic-named sub-headings
had ZERO extracted steps before this fix, not merely mis-extracted
ones -- flagged to Anna before implementing, given the reach.

**Fix, on Anna's go-ahead ("corrijamos eso antes de seguir con cosas más
grandes")**: generalized path 5 of `_extract_procedural_steps` from
"numbered sub-heading under a procedural ancestor" to "ANY sub-heading
under a procedural ancestor, excluding a boilerplate title
(`_BOILERPLATE_SECTIONS`) or an `Example N:` walkthrough heading" --
the numbered form is now just one instance of the general rule, not a
separate case. The now-redundant `_NUMBERED_SUBHEADING` pattern was
removed; a small `_LEADING_NUMBER` pattern strips a numeric prefix from
the extracted step text when one is present, purely cosmetic.

Verified by diffing, not just counting (per the SCOPE_TRIGGER_MISMATCH
gate-change lesson):

| Check | terminalskills before -> after | mukul975 | author corpus |
|---|---|---|---|
| METHODOLOGICAL_VACUITY | 16 -> 0 | 1 -> 1 (unchanged) | 1 -> 1 (unchanged) |
| REQUIREMENT_WITHOUT_CHECK | 110 -> 110 (identical skill set, diffed) | 23 -> 23 | 21 -> 21 |
| MISSING_FAILURE_MODE | 33 -> 39 (skills with real steps now in scope for the check for the first time; same template, still no failure vocabulary) | 40 -> 40 | 0 -> 0 |
| CHECK_WITHOUT_ORACLE | 8 -> 8 | 326 -> 326 | 7 -> 7 |

Zero effect on mukul975/the author's own corpus -- neither uses this
exact topic-sub-heading convention. 2 new compiler-level tests (a
genuine topic-named sub-heading extracted as a step; a boilerplate
sub-heading under the same procedural ancestor correctly excluded).
Full suite and mutation gate green.

## Summary

Both mechanism E (section-title substring collision) and the topic-
named-sub-heading step-extraction gap are now fixed, verified by diff
against held-out, mukul975, and the author's corpus. REQUIREMENT_
WITHOUT_CHECK's remaining true positives and SCOPE_TRIGGER_MISMATCH's
already-accepted lexical-vs-semantic residual are untouched, correctly.

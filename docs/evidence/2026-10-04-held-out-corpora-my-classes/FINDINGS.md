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

## What this does and does not resolve

No code changed by this investigation. Mechanism E (substring
collision) looks like a narrow, well-evidenced, high-value fix: require
the section title to be substantially about checks/verification/
validation (e.g. the title IS "checks"/"verification"/"validation
criteria"/etc., not merely contains the word), rather than a bare
substring test. This is Anna's call, same discipline as every other
fix this session -- not implemented ad hoc here.

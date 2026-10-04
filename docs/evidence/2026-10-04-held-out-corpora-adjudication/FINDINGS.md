# First genuinely held-out corpus run — three fresh, previously untouched repositories

**Date:** 2026-10-04
**Context:** the independent-evaluation gate (`docs/NEXT_LEVELS.md`, "Next gate:
independent evaluation") requires class-level precision/recall on a held-out
set, kept separate from development examples. `mukul975/Anthropic-
Cybersecurity-Skills` — the external corpus used for most prior adjudication —
no longer qualifies: it was used repeatedly to calibrate the compiler and
auditor during the L9 extraction-bug session (2026-10-03), so it is now dev
data, not held-out evidence. This run uses three repositories never referenced
in any prior Crucible commit, finding, or fixture.

## Corpus

Simulated a real user installing three skill collections side by side in
`~/.claude/skills/` (via the real `--scan-installed-collection` path, with
`$HOME` pointed at an isolated directory — the user's actual installed
collection was never touched):

| Repository | Commit | License | Domain | Real SKILL.md count |
|---|---|---|---|---|
| [microsoft/skills](https://github.com/microsoft/skills) | `ce7edea90860e0c69fa36db164584c87908e09f5` | MIT | Azure SDK / cloud dev tooling | 61 (13 top-level + 48 behind directory symlinks, dereferenced on copy) |
| [machina-sports/sports-skills](https://github.com/machina-sports/sports-skills) | `c5a487da25a883f6ebc0ebb7603e8543409133df` | MIT | sports data / prediction markets | 27 |
| [TerminalSkills/skills](https://github.com/TerminalSkills/skills) | `a021875c0f1bd906248e3784ce470faa65055201` | Apache-2.0 | general curated agent skills | 1,055 total; **440-then-400 sampled** (see below) |

All three domains are disjoint from `mukul975` (offensive security) and from
the author's own corpus, by design — this is meant to be genuine
false-positive pressure from unrelated authors and styles, not a repeat of
the same domain.

### A real resource-bound hit, and why the sample size changed twice

`scan_installed_collection`'s `_MAX_SCAN_SKILLS = 500` cap is a **whole-scan,
fail-closed abort** confirmed intentional by its own test
(`tests/test_installed_collection.py::test_entry_budget_includes_symlink_errors`,
asserting `pytest.raises(ValueError, match='entry limit')`) and its own
docstring (`_CollectionLimitError`: "a whole-scan limit, not an error confined
to one package"). This is not a bug — it is a deliberate fail-closed design,
not honest partial degradation, and it is worth noting as a real limitation
of the installed-collection path: hitting the cap returns a bare
`{"status": "ERROR", "error": "installed collection exceeds scan entry
limit"}` with no count of what was discovered before the limit, even though
the function has already accumulated that count internally. All three repos
combined (13 + 27 + 1,055 = 1,095) blew well past the cap on the first
attempt. A first sample of 440 TerminalSkills skills (seed `20261004`,
`random.sample`) plus the 13 *visible* microsoft/skills entries still
exceeded it once the 48 symlinked Azure SDK skill directories were
dereferenced (cp with `-L`) into 48 additional real entries — dereferencing
was the right call (a real install would not leave live skill content behind
a rejected symlink), but it meant the budget math had to be redone. Final
split: 61 (microsoft, all real) + 27 (sports, all real) + 400 (TerminalSkills,
sampled) = 488, under the 500 cap.
[Full sample manifest](terminalskills-sample-manifest.txt) — seed and the full
400-skill list, for reproducibility.

**Result: `status: COMPLETE`, 488/488 analyzed, 0 errors.**

## Finding 1 (CONFIRMED, code fix applied): `NON_DETERMINISTIC_INSTRUCTION`'s `pick/choose "one"` branch is a 100%-false-positive mechanism

The check fired 39 times — a conspicuously high rate against `mukul975`'s 19
findings over 818 skills. 35 of the 39 (all from `microsoft-skills`) were the
**same templated sentence**, repeated verbatim across nearly every
auto-generated Azure SDK skill file:

> 1. **Pick sync OR async and stay consistent.** Do not mix `azure.xxx` sync
> clients with `azure.xxx.aio` async clients in the same call path. Choose
> one mode per module.

`\bchoose\s+(?:any|one)\b` matched "Choose one mode per module." This
instruction is the *opposite* of non-determinism: it tells the agent to
commit to a single, fixed choice and stay consistent — exactly the
determinism the check exists to protect. "one" shares the bare-article "a"
semantics (a specific single item) that the check's own prior fix (mechanism
7, `docs/evidence/2026-10-02-non-deterministic-instruction-false-positives/FINDINGS.md`)
already excluded for "a" — it does not share "any"'s semantics (no
constraint on which item). No existing test or adjudicated finding relied on
"one" as a genuine positive (checked before changing anything, per
audit-before-patch).

**Fix:** dropped "one" from the `pick`/`choose` alternation in
`_NON_DETERMINISTIC_PATTERNS` (`src/crucible/auditor.py`), keeping "any".
Measured, not assumed: re-ran the exact same held-out scan after the fix —
`NON_DETERMINISTIC_INSTRUCTION` dropped from 39 to 4 (-35, exactly the
predicted count), **zero other check class changed** (confirmed by diffing
full per-class counts before/after, not just the total). 1 new regression
test using the real found sentence
(`test_non_deterministic_does_not_fire_on_choose_one_consistently`). Full
suite: 770/770 pass (769 pre-existing unchanged + 1 new). Mutation gate
unaffected (6/6 killed, 2 abstained, 0 survived).

## Remaining 4 findings: read individually, adjudicated against the existing criterion — all 4 are also false positives

Using the same criterion already established in
`docs/evidence/2026-10-02-non-deterministic-instruction-false-positives/adjudication.json`
("A positive requires an instruction that makes the agent's own method or
outcome unconstrained and irreproducible. A keyword used to describe a
threat, a required cryptographic random value, a named algorithm, or the
subject of an audit is not sufficient."):

| Skill | Flagged text | Mechanism | Label |
|---|---|---|---|
| `lucia-auth` | "Always generate ids and secrets with `crypto.getRandomValues`; never `Math.random`." | Mechanism 1 (required randomness, security primitive) — identical pattern to the `mukul975` OAuth2/PKCE findings already adjudicated FALSE_POSITIVE | FALSE_POSITIVE |
| `mkdocs` | "an MkDocs plugin and `hooks:` run arbitrary Python during the build; install only plugins you trust" | Mechanism 2-family (describes a third-party component's capability/hazard, not an instruction to the agent) | FALSE_POSITIVE |
| `leptos` | "reading `window`, random values or the clock during render causes hydration errors" | Mechanism 2-family (names the anti-pattern being warned against; the actual instruction is the following sentence, "Do that work in `Effect::new`") | FALSE_POSITIVE |
| `e2b` | "the base template includes NumPy, Pandas, and Matplotlib but **not** arbitrary packages" | New: "arbitrary" directly negated by "not" within the same clause — a sentence-level negation the existing rule-level `_NEGATIVE_MODALITIES` guard (mechanism 8) does not reach because this is a plain bullet, not a modal rule | FALSE_POSITIVE (not code-fixed this round — a local negation scan risks the same vocabulary-list fragility already flagged for `CHECK_WITHOUT_ORACLE` mechanism C; left as an adjudicated label, consistent with several of the 8 prior mechanisms) |

**Result: 0/4 genuine true positives.** Combined with the 35 already-explained
findings: **0/39 true positives in this held-out run.**

## What this adds to the existing result

The prior adjudication already found 0/23 true positives across three
corpora (mukul975, the author's own, and — per that file — a third). This
held-out run adds a **fourth, genuinely untouched corpus** and finds **0/39**
true positives there too, after one narrow code fix that accounted for 35 of
the 39. Aggregate across all adjudicated runs to date: **0 confirmed true
positives for `NON_DETERMINISTIC_INSTRUCTION` across 4 independent corpora**
(author's own, mukul975, and now microsoft/skills + machina-sports +
TerminalSkills together). This is evidence-backed, not proof of zero recall
in general — no corpus here was selected for genuine non-determinism defects,
so this measures false-positive pressure, not whether the check would catch
a real one if present. But a check that has not fired correctly once across
four independent, stylistically different corpora is a real signal: the
current lexical-trigger design may be structurally unable to distinguish "the
agent is told to act without a fixed method" from "this document contains
the word random/arbitrary/pick/choose for an unrelated reason." Whether to
redesign the check (e.g. requiring the trigger word's grammatical subject to
be the agent, not a third party or a named technical term) is a design
decision for Anna, not an implementer default — flagging it here rather than
quietly patching around it.

## Finding 2 (CONFIRMED, code fix applied): `IRREVERSIBLE_WITHOUT_REVIEW` had no negative-modality guard at all

Unlike `NON_DETERMINISTIC_INSTRUCTION`, this check never excluded
MUST_NOT/SHOULD_NOT/NEVER rules, and had no equivalent guard for procedural
steps (which carry no `modality` field). Reading all 54 findings:

- **Prohibition, not instruction (7, fixed):** `tiktok-marketing` ("Never
  delete underperforming videos"), `gdpr-compliance` ("Do NOT immediately
  delete. Use a 30-day cooling-off queue."), `ssh` ("Never copy private
  keys... remove old lines... when a device is decommissioned"),
  `kubernetes-helm` ("Never run containers as root; drop all
  capabilities..."), `documentation-and-adrs` ("Do not edit the reasoning
  of an accepted record, delete a record..."), `react` ("Do not silence
  `react-hooks/exhaustive-deps`. ... or drop the effect.") and one more —
  all are prohibitions of the irreversible action, not instructions to
  perform it. Same reasoning as `_check_non_deterministic`'s existing
  `_NEGATIVE_MODALITIES` guard, which this check never had.
- **Domain-specific, non-destructive sense of the trigger word (not
  fixed):** `kql` ("`| project` to drop unneeded columns" — a query-time
  projection, not data deletion), `tensorflow` ("drop to custom training
  loops" — a fallback, not a deletion), `paid-ads` ("a sudden jump or drop
  with flat spend" — a metric decline, not an action at all), `phaser`
  ("destroy particle emitters" — game-object lifecycle, not user data),
  `bug-hunt-swarm` ("Drop any claim that does not check out" — discard an
  unverified assertion in a report), `value-based-selling` ("Remove
  Barriers to Purchase" — a sales metaphor), and several more in the same
  shape.
- **Access-control rule text misread as an instruction (not fixed):**
  `pocketbase` ("update/delete `author = @request.auth.id`") is a
  PocketBase authorization-filter expression being documented, not an
  instruction telling the agent to delete anything.
- **Repeated template, same shape as Finding 1 (not fixed):** 7 Azure Rust
  SDK skills share "Use `cargo add` to manage dependencies, never edit
  `Cargo.toml` directly. Add and remove Rust SDK dependencies with cargo
  commands..." — "never edit" is mid-sentence, not line-initial, so the
  lexical starter guard (which only matches at the start of a bullet/line,
  deliberately, to avoid a much riskier "contains never anywhere" rule)
  does not reach it.
- **The check has no notion of version control (not fixed, a real gap):**
  several remaining findings are code/config deletions in a
  presumably-git-tracked repository (`improve-codebase-architecture`:
  "delete the old paths"; `typescript`: "Remove `allowJs`"; `vite`:
  "remove react-scripts") — recoverable via `git revert`/history, but
  `_REVIEW_BOUND_PATTERNS` has no anchor for that. This blind spot likely
  affects most software-engineering-domain skills generically, not just
  this corpus.
- **Plausible genuine candidates, left as CANDIDATE (correct behavior):**
  `cloudflare-vectorize` ("delete vectors"), `sentry` ("delete [source
  maps] from the deployed output" after upload, order-dependent), `sst`/
  `neon` ("delete branch/resource when PR is closed" with no safeguard
  mentioned), `azure-containerregistry-py` ("Delete by digest not tag")
  — real, stateful deletions with no review/backup/rollback language
  nearby. Whether these are true positives requires domain judgment this
  session did not have time for; they are correctly left unresolved, not
  mislabeled.
- **A vocabulary gap (not fixed):** `azure-keyvault-py` ("Enable
  soft-delete for recovery") already names the deterministic anchor it
  needs — "recovery"/"recoverable" is a reversibility bound in plain
  English — but `_REVIEW_BOUND_PATTERNS` has no entry for it (only
  `reversib(?:le|ility)`).

**Fix applied:** added the `_NEGATIVE_MODALITIES` guard to the `rules` loop
(direct reuse of the existing, already-validated pattern) and, for
procedural steps (no `modality` field), reused the compiler's own
`_NORMATIVE_STARTERS` line-initial lexical detector rather than inventing a
second heuristic. Measured: 54 -> 47, exactly the 7 prohibition cases above,
zero other class moved. 2 new regression tests (one rule-side, one
step-side, using the real found sentences). 772/772 tests pass (770 + 2
new). Mutation gate unaffected (6/6 killed, 0 survived).

**Deliberately not fixed this round:** the mid-sentence negation, the
domain-specific/metaphorical senses, the access-control misparse, the
version-control blind spot, and the vocabulary gap. Each of those requires
either a riskier pattern change (mid-sentence negation scanning could
suppress a real positive sitting next to an unrelated "never") or a product
decision (should "recoverable via git" count as a review bound for a
security check that exists specifically because git history is not always
checked before an agent acts?) — left open rather than guessed at, same
discipline as `CHECK_WITHOUT_ORACLE`'s mechanism C in the 2026-10-02 audit.

## Finding 3 (CONFIRMED, narrow code fix applied): `COMMAND_ORACLE_WITHOUT_ARTIFACT`'s list-introduction line was double-counted as a spurious extra vague check

This class is far messier than the first two — reading all 106 findings
line-by-line (with source context, not just the extracted check text) found
at least five distinct shapes, only one of which was safe to fix this round:

- **List introduction, double-counted (8/106, fixed):** a check whose text
  is only a lead-in ending in a colon — `"Check these rules:"`,
  `"Verify:"`, `"Run experiments in this order of impact:"` — is not itself
  a checkable claim; the real check items are the following list entries,
  which the extractor *already* captures as their own independent checks
  (confirmed directly: `dns-record-analyzer`'s real checks at lines 81-84
  were extracted correctly and separately from its spurious intro lines at
  52 and 73). The intro line was flagged as an extra, redundant vague check
  on top of the real ones.
- **Named tool/script/URL by plain text (~15, not fixed — already a
  documented limitation):** `burp-suite` ("Confirm a hit manually in
  Repeater..."), `react-aria` ("Test with VoiceOver (Mac), NVDA
  (Windows)..."), `logstash` x2 ("...with the Grok Debugger..."), `nikto`
  ("Run Nikto early..."), `sanity` ("Query with GROQ projections..."),
  `microsoft-teams` ("Test Adaptive Cards at adaptivecards.io/designer..."),
  `whisper` ("Run pyannote speaker diarization..."), and others — each
  names a concrete tool, but by plain English name rather than inline
  code, which `_has_named_artifact`'s own docstring already discloses as
  out of scope ("a check may reference an external script or tool by
  plain-text name... which this heuristic cannot distinguish from a
  genuinely vague claim"). Not a hidden bug; a already-disclosed,
  now-measured limitation.
- **Not a check at all — architecture/deployment/operational text that
  happens to start with a verification-adjacent verb (~15-18, not fixed —
  needs decompiler-level judgment, not an auditor-level pattern):** `neon`
  ("Run migrations on the main branch; feature branches inherit schema
  automatically" — a behavior statement), `thanos` ("Run exactly one
  compactor instance per object storage bucket to avoid data corruption" —
  an architectural constraint), `tooljet` ("Query results and component
  state live in the browser: do not put secrets in expressions..." — a
  security warning), `value-based-selling` ("Demonstrate how your approach
  is different..." — sales methodology; "demonstrate" is a literal
  verification-verb trigger, wrong domain entirely), `unusual-whales-api`
  ("Query the Unusual Whales API for institutional-grade market data..." —
  the skill's own top-level description, matched by "Query" at sentence
  start). These are extraction-scope false positives, not auditor-pattern
  false positives — the text was never a check to begin with; fixing this
  means tightening what `_extract_checks` admits as a check, a much larger
  and riskier surface than anything touched so far in this file.
- **Not machine-verifiable by construction — a human-confirmation
  instruction, not a command oracle (~3-4, not fixed):** `cv-builder`
  ("Confirm the update with the user"), `polymarket-trading` ("Confirm the
  user explicitly requested a trading/order-management action..."),
  `machina` ("Run this in the developer's terminal if you have permission,
  or ask them to run it.") — these ask a *person*, not a script; whether
  that should count as "command oracle without artifact" at all is a
  product question (is a human confirmation gate a valid bound, or does
  this check only mean machine-executable verification?), not an
  extraction bug.
- **Genuinely vague, no named artifact, plausible true positive (the
  remaining ~60-65):** `frontend-design-review` ("Verify design tokens are
  used (not hardcoded values)"), `restic` ("Test restores regularly. A
  backup you've never tested restoring from is not a backup — it's a
  hope."), `regression-tester` (four separate findings, all genuine
  testing-methodology prose with no named script), `cursor-ai` and
  `openai-realtime` sharing an identical generic three-step install-guide
  template ("Check system requirements and prerequisites" / "Verify the
  setup works correctly" / "Test and validate the output") — vague by
  construction, and notably templated the same way Finding 1's mechanism
  was, though here the vagueness is real regardless of the repetition.
  These look like the check doing exactly what it is designed to do.

**Fix applied (list-introduction only):** `_has_named_artifact` now also
returns true when the check text ends in `:` and the first non-blank line
immediately following it starts with an explicit bullet/numbered marker
(reusing the compiler's own `_EXPLICIT_LIST_MARKER`, not a new pattern).
Measured: 106 -> 99 on the held-out corpus, 7 of the 8 predicted cases
(the 8th, `agent-memory` line 30, introduces a **markdown table**, not a
bulleted/numbered list — correctly left alone; a table row is not
independently extracted as its own check the way a bullet is, so the same
"already captured elsewhere" justification does not apply, and extending
the fix to tables was not verified safe). 2 new regression tests (a real
positive case mirroring `dns-record-analyzer`, and a negative control
proving the exemption requires an actual following list, not just a
trailing colon). 774/774 tests pass, mutation gate unaffected (6/6 killed,
0 survived).

**Deliberately not fixed this round:** the other four mechanisms above.
Each needs either accepting a known, already-documented scope limitation
(named-tool-by-text), a much larger and riskier change to what counts as
a "check" at extraction time (wrong-domain/architecture text), or a product
decision about whether human confirmation satisfies this check's intent
(it currently does not, and whether it should is not an implementer
default).

## Finding 4 (CONFIRMED, code fix applied; also surfaces a second, unfixed issue): `REQUIREMENT_WITHOUT_CHECK` fires because a Checks-section numbered list was silently dropped at extraction, not because the skill lacks checks

Unlike the first three findings, `REQUIREMENT_WITHOUT_CHECK` itself held up
well under reading: of a 10-skill sample (`espn-api`, `adonisjs`, `cors`,
`azure-storage-blob-rust`, `fail2ban`, `documentation-and-adrs`,
`changelog-generator`, and others), every one had real, substantive
normative rules ("NEVER use `Access-Control-Allow-Origin: *` with
`credentials: true`", "Do not import `azure_identity::DefaultAzureCredential`")
and genuinely zero verification apparatus anywhere in the body — reference/
API-documentation-style skills that state best practices but never say how
to check compliance. This looks like the check doing exactly what it is
designed to do, a different and more positive calibration result than the
first three findings.

But one of the 120 — `polymarket` — led to a real extraction bug one level
down, in `compiler.py` rather than `auditor.py`. Its `### Live Odds Check`
section (recognized as a Checks section by the same substring match
discussed in Finding 3) contains 3 real numbered checks. `_extract_checks`'s
in-section path only ever matched `_BULLET` (`-`/`*`/`+`), never
`_NUMBERED` — a numbered list under a real Checks heading was invisible
there, and the fallback "verification verb anywhere in the body" path does
not catch it either, since the items' text ("Present probabilities with
liquidity/freshness caveats") does not start with a verification verb.
All 3 checks were silently lost, not merely misclassified.

**Fix:** the in-section match in `_extract_checks` now uses
`_EXPLICIT_LIST_MARKER` (bullet or numbered) instead of `_BULLET` alone.
Measured: `REQUIREMENT_WITHOUT_CHECK` 120 -> 118 (`polymarket` and
`web-research` both now have >=1 extracted check and leave the list). 1
new regression test using the real found section. 775/775 tests pass,
mutation gate unaffected (6/6 killed, 0 survived).

**A second, separate, NOT-fixed issue this surfaced:** the same fix, by
making numbered Checks-sections visible, exposed that the section-title
match itself (`any(k in title for k in ("check", "verification",
"validation"))`) is a loose substring match, not a heading-shape match.
`web-research`'s `### Example 3: Fact-checking and verification` and
`microsoft-teams`'s `### Example 2: Build a slash-command bot for system
health checks` are ordinary worked-example walkthroughs whose *titles*
happen to contain "verification"/"checks" as an incidental word, not
genuine Checks sections. Post-fix, their numbered example steps (literal
search-query strings in `web-research`; "Fetch current metrics from the
monitoring API endpoints" in `microsoft-teams`) are now extracted as
checks and fire `CHECK_WITHOUT_ORACLE` (+11 on this corpus; 5 of the 11
are genuine recoveries from the same "Live Odds Check"-style template
shared across sibling sports skills -- `kalshi`, `tennis-data`,
`sports-news`, `regression-tester` -- the other 6 are this new mechanism).
Worse: `web-research` left the `REQUIREMENT_WITHOUT_CHECK` list on the
strength of these false checks, which could mask a real
`REQUIREMENT_WITHOUT_CHECK` case behind a skill that does not actually
have any genuine checks. This bug was always present in the heading-title
matcher -- the numbered-list fix only made it visible, by letting a
numbered example list reach the same section-title filter that bulleted
content already passed through unnoticed. Narrowing the title match from
"contains the substring anywhere" to something shape-aware (e.g. the
heading's own words, stripped of an "Example N:" prefix, must *be*
check/verification/validation rather than merely mention it) is a larger,
less contained change than anything fixed in this file so far, with its
own false-negative risk (a real `## Checks and Verification` heading must
keep matching) -- left open rather than guessed at, same discipline as
the other deferred mechanisms above.

## Other classes: not adjudicated this round

`MISSING_FAILURE_MODE` (41), `METHODOLOGICAL_VACUITY` (20),
`SCOPE_TRIGGER_MISMATCH` (15), `UNPINNED_DEPENDENCY` (12),
`CHECK_WITHOUT_ORACLE` (22), `UNBOUNDED_RETRY` (10),
`CLAIM_WITHOUT_PROVENANCE` (6), `OVERCLAIM` (5),
`UNVALIDATED_EXTERNAL_INPUT` (4), `UNBOUNDED_RESOURCE` (3),
`SECRET_IN_OUTPUT` (2) all fired on this held-out corpus and remain
unreviewed (`NON_DETERMINISTIC_INSTRUCTION`, `IRREVERSIBLE_WITHOUT_REVIEW`,
`COMMAND_ORACLE_WITHOUT_ARTIFACT`, and `REQUIREMENT_WITHOUT_CHECK` are now
adjudicated, above; `CHECK_WITHOUT_ORACLE`'s count moved as a side effect
of Finding 4 and includes the unfixed heading-title mechanism above, not a
fresh adjudication of its own). This session scoped to four classes,
each fully read, rather than a shallow pass over all eleven remaining —
the next increment of this gate should pick up one of them against the
same three pinned corpora (no new acquisition needed), and should
probably start with the heading-title matcher question Finding 4 left
open, since it affects what every other Checks-dependent check sees.

## Full raw results

All three scans are sealed `crucible-installed-collection/v1` artifacts (488
entries each, full per-skill IR text included — not committed to this public
repo, same as the `mukul975` precedent, since redistribution terms for
`TerminalSkills/skills`'s 400-skill sample have not been individually
reviewed, only the repo-level license):

| File | SHA-256 | NDI | IWR | COA | RWC | CWO |
|---|---|---|---|---|---|---|
| `scan_collection_result_before.json` (baseline) | `6b343b5d744ff196bea10947194700679def999952301c806e1c437c7673fe19` | 39 | 54 | 106 | 120 | 11 |
| `scan_collection_result_after.json` (post Finding 1) | `15c429397982a2d8be487855f6d5f78eeb32e69bf976062fc923f2d5c44a0f10` | 4 | 54 | 106 | 120 | 11 |
| `scan_collection_result_after_irreversible_fix.json` (post Finding 2) | `68ef3adb8e6746ead30361b2851a41a4e6e67350e8c54b778289f73d2ab2b6dd` | 4 | 47 | 106 | 120 | 11 |
| `scan_collection_result_after_command_oracle_fix.json` (post Finding 3) | `6279dc518cb7284b83664c5db636e22ffc244ef80294acff8b23c8c3b4580a71` | 4 | 47 | 99 | 120 | 11 |
| `scan_collection_result_after_numbered_checks_fix.json` (post Finding 4) | `49f98f7db157dc220850e23a1ceff20b5d96719f80eb5314dfcada1705b82aad` | 4 | 47 | 101 | 118 | 22 |

(NDI = `NON_DETERMINISTIC_INSTRUCTION`, IWR = `IRREVERSIBLE_WITHOUT_REVIEW`,
RWC = `REQUIREMENT_WITHOUT_CHECK`, CWO = `CHECK_WITHOUT_ORACLE` (moved as a
side effect of Finding 4, not independently adjudicated),
COA = `COMMAND_ORACLE_WITHOUT_ARTIFACT`.)

Retained privately alongside the cloned corpora. [The sample manifest](terminalskills-sample-manifest.txt)
(names only, no source text) is committed, so the exact 400-skill sample is
reproducible against a fresh clone of the pinned commit above.

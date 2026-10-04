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

## Other classes: not adjudicated this round

`COMMAND_ORACLE_WITHOUT_ARTIFACT` (106), `REQUIREMENT_WITHOUT_CHECK` (120),
`IRREVERSIBLE_WITHOUT_REVIEW` (54), `MISSING_FAILURE_MODE` (41),
`METHODOLOGICAL_VACUITY` (20), `SCOPE_TRIGGER_MISMATCH` (15),
`UNPINNED_DEPENDENCY` (12), `CHECK_WITHOUT_ORACLE` (11),
`UNBOUNDED_RETRY` (10), `CLAIM_WITHOUT_PROVENANCE` (6), `OVERCLAIM` (5),
`UNVALIDATED_EXTERNAL_INPUT` (4), `UNBOUNDED_RESOURCE` (3),
`SECRET_IN_OUTPUT` (2) all fired on this held-out corpus and remain
unreviewed. This session scoped to one class, fully adjudicated, rather than
a shallow pass over all of them — the next increment of this gate should pick
up one of the remaining classes against the same three pinned corpora (no
new acquisition needed).

## Full raw results

Both scans are sealed `crucible-installed-collection/v1` artifacts (488
entries each, full per-skill IR text included — not committed to this public
repo, same as the `mukul975` precedent, since redistribution terms for
`TerminalSkills/skills`'s 400-skill sample have not been individually
reviewed, only the repo-level license):

| File | SHA-256 | `NON_DETERMINISTIC_INSTRUCTION` count |
|---|---|---|
| `scan_collection_result_before.json` (pre-fix) | `6b343b5d744ff196bea10947194700679def999952301c806e1c437c7673fe19` | 39 |
| `scan_collection_result_after.json` (post-fix) | `15c429397982a2d8be487855f6d5f78eeb32e69bf976062fc923f2d5c44a0f10` | 4 |

Retained privately alongside the cloned corpora. [The sample manifest](terminalskills-sample-manifest.txt)
(names only, no source text) is committed, so the exact 400-skill sample is
reproducible against a fresh clone of the pinned commit above.

# ADR-0023: Verification-Starter Continuation Lines and Indented Code Fences

**Status:** Accepted
**Date:** 2026-10-03
**Reversibility:** high; both fixes narrow over-extraction, no schema
change, no new finding class

## Context

The user pushed back on the pace of this session: 27 days remain, and
the priority is making sure the CLI's three scan modes (one skill, a
repository, a user's installed skills) actually work well on real data
— not adding more features. This ADR documents what that real-data
validation found.

Running `crucible --scan-installed` against the user's actual local
collection (~100 unique skills after deduplication, discovered across
multiple tool config directories) surfaced `COMMAND_ORACLE_WITHOUT_ARTIFACT`
(added earlier this session) on 58 of 120 total findings — nearly half.
That ratio, on a real and much larger corpus than the 10-skill diverse
corpus this check was validated against, was the signal that something
was wrong, and it was not the new check's calibration.

## Decision

Two real, pre-existing (not introduced this session) extraction bugs
were found and fixed in `compiler.py`, both confirmed against specific
real lines in the user's installed skills before being generalized into
a fix and a synthetic regression test (the test fixtures are invented
examples illustrating the bug shape, not quotes from the user's files).

### Bug A: a bare verification verb matched mid-sentence continuation lines

`_VERIFICATION_STARTER` (`_extract_checks`'s "anywhere in the body"
mechanism) matches a line starting with a verb like `run`, `does`,
`check`, `confirm`, etc., with an OPTIONAL bullet/number marker. The
marker being optional was deliberate — it is what lets a standalone
imperative sentence like "Run the analysis." become a check even when
it is not written as a bullet. But without the marker, the regex cannot
tell "a new sentence that happens to start with this word" from "a
hand-wrapped continuation line of a longer, unrelated sentence" — e.g.
a numbered list item's text wrapped across two physical lines, where
the second line is indented and happens to start with "does" or
"confirm" as an ordinary English word, not a check.

Measured effect: roughly 40 of the 58 flagged findings were exactly
this — sentence fragments like "...the sequence / does: invite
yourself, accept, transfer..." (a continuation, not a check) rather than
genuine vague oracles. These fragments were invisible before this
session because they already satisfied `oracle_kind != "unknown"` (the
fragment itself usually contains one of the matched verbs), so neither
`CHECK_WITHOUT_ORACLE` nor `REQUIREMENT_WITHOUT_CHECK` ever flagged the
skill as lacking a check — the garbage extraction was silently masking
a real absence of checks on some of those skills.

**Fix:** a bare-verb match with no explicit bullet/number marker on the
same line is only accepted if the previous line marks a real
sentence/paragraph boundary (blank, a heading, or ending in
`.`/`!`/`?`/`:`, optionally followed by a markdown closer like `` ` ``/`*`/
quotes). An explicit marker on the matched line itself is unambiguous
and bypasses the guard entirely — `test_explicit_bullet_bare_verb_is_a_
check_regardless_of_previous_line` pins this. The existing legitimate
case (`test_verification_starter_outside_checks_section`, three
standalone one-line sentences) is unaffected, since each of those three
lines' predecessor already ends in `.`.

### Bug B: `_CODE_FENCE` did not recognize an indented ``` fence

`_CODE_FENCE = re.compile(r"^```")` required the fence at column 0. A
fenced code block nested inside a list item is conventionally indented
to match the item's content (standard CommonMark), so an indented fence
was never recognized as code at all — every line inside it, including
embedded YAML/shell syntax, was scanned as ordinary prose. Confirmed
against a real installed skill: an indented ` ```yaml ` block under a
numbered step contained a `run: |` YAML mapping key, extracted as a
bogus check (`run` is a verification verb) because the surrounding fence
was invisible to `_code_block_lines`.

**Fix:** `_CODE_FENCE = re.compile(r"^\s*```")` — leading whitespace
allowed, zero-indentation still matches exactly as before.

## A third, larger, NOT-yet-fixed finding: multi-line bullet wrapping

Fixing A and B (58 → 35 `COMMAND_ORACLE_WITHOUT_ARTIFACT` findings,
measured live) surfaced a third, structurally bigger issue while
inspecting the remaining 35: several are explicitly-bulleted items
(`- Where does X grant Y for a` / `  long session?`) whose text wraps
across two physical lines, where `_BULLET`'s per-line regex only
captures the FIRST physical line — silently truncating the actual
sentence, including, in these specific cases, the trailing `?` that
would have classified them as `oracle_kind: "question"` instead of
`"command"`.

This is not scoped to checks: `_extract_rules` and the relations
extractors (`composes_with`/`delegates_to`) use the same per-line
regex-match pattern (`for index in range(...): line = lines[index];
...`), so a multi-line-wrapped RFC-2119 rule or a multi-line reference
bullet would be truncated the same way. **This was not fixed in this
session** — joining a wrapped continuation into one logical bullet/rule
needs a shared preprocessing pass (deciding where a continuation ends:
a blank line, a new marker, a heading, a dedent, a code fence) used
consistently by every line-based extractor, which is a materially larger
change than A/B above and deserves its own focused, tested pass rather
than being folded into this one. Tracked as open work, not closed here.

## Alternatives rejected

- **Weaken or revert `COMMAND_ORACLE_WITHOUT_ARTIFACT` instead of fixing
  the extractor.** Rejected: the check's own logic was correct throughout
  — every one of the 35 remaining findings, re-inspected after A+B,
  reflects a genuinely vague command-oracle check (no named script,
  verified by hand against the real text). The noise was upstream, in
  what counted as a "check" in the first place, not in how command
  oracles are judged once extracted.
- **Require an explicit bullet marker unconditionally for the
  verification-starter mechanism.** Rejected: this would lose the
  legitimate standalone-sentence case the mechanism was built for
  (`test_verification_starter_outside_checks_section`), trading one
  false-positive class for a false-negative one.
- **Fix the multi-line bullet-wrapping issue in this same pass.**
  Rejected for scope discipline: it touches three extractors
  (rules/checks/relations) at once and needs its own design for where a
  continuation legitimately ends; bundling it here risks a rushed,
  under-tested fix to exactly the kind of foundational correctness work
  the user asked to slow down and do properly.

## Consequences

Accepted now:
- Two real extraction bugs fixed, both confirmed against real text
  before being generalized into a regex-level fix.
- Measured, not assumed: `COMMAND_ORACLE_WITHOUT_ARTIFACT` findings on
  the user's real ~100-skill collection dropped from 58 to 35 (-40%);
  `REQUIREMENT_WITHOUT_CHECK` rose from 16 to 24 and
  `METHODOLOGICAL_VACUITY` from 2 to 3 — skills that were incorrectly
  registering as "having checks" (via garbage fragment extraction) now
  correctly surface as lacking them. Noise went down and real signal
  went up in the same measurement.
- 4 new falsifiable tests (synthetic fixtures, not quotes from the
  user's files): the continuation-line guard, its boundary-preserving
  counterpart, explicit-marker bypass, and the indented-fence case. Full
  suite green, no regressions.

Deferred, tracked explicitly, not closed:
- Multi-line bullet/rule text joining across rules, checks, and
  relations extraction (the third finding above).

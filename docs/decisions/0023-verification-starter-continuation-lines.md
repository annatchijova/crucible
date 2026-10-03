# ADR-0023: Verification-Starter Continuation Lines and Indented Code Fences

**Status:** Accepted
**Date:** 2026-10-03
**Reversibility:** high; all three fixes narrow over-extraction or
recover truncated text, no schema change, no new finding class

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

Deferred at first, then closed the same day per direct user request
("sí, con el fix"):
- Multi-line bullet/rule text joining across rules, checks, and
  relations extraction (the third finding above).

## Addendum 2026-10-03: the third finding, fixed

Two shared join helpers, used by every per-line extractor that needed
one: `_join_marked_continuation` (an explicit bullet/number marker --
joins until a blank line, heading, code fence, or the next marker;
multiple complete sentences within one item are all kept, since a
marked item has no sentence-boundary stopping rule) and
`_join_unmarked_sentence` (a bare modal/imperative/verification-verb
line with no marker -- joins only until the accumulated text reaches a
real sentence boundary, so that several independent one-line sentences
in a row, each already complete, are never merged into one).

Wired into `_extract_rules` (all three styles: RFC-2119 modals, negative
starters, imperative starters), `_extract_checks` (both the
Checks-section-bullet mechanism, bounded by the section's own end, and
the anywhere-in-body verification-starter mechanism), and
`_extract_procedural_steps` (numbered lists in and outside dedicated
sections, and action-verb bullets). `_extract_relations`
(`composes_with`/`delegates_to`) was deliberately left untouched: its
bullet values are short skill-name identifiers, not prose, so wrapping
is not a real-world case there.

Measured again on the same real ~100-skill collection:
`COMMAND_ORACLE_WITHOUT_ARTIFACT` dropped further, 35 → 31 — the
remaining real cases from ADR-0023's measurement (bulleted questions
whose `?` landed on a wrapped second line, previously truncated before
the question mark) now correctly join and reclassify as `oracle_kind:
"question"` instead of `"command"`, confirmed directly against the real
IR output. Several other checks' counts moved too
(`IRREVERSIBLE_WITHOUT_REVIEW` 18→22, `OVERCLAIM` 4→9,
`NON_DETERMINISTIC_INSTRUCTION` 2→5, `LLM_IN_DECISION_PATH` 0→2) because
those checks now see each item's COMPLETE text instead of a
first-line-only truncation. Spot-checked one `LLM_IN_DECISION_PATH` case
by hand against the real source: the join itself is correct (it is one
bullet's real continuation, not two unrelated bullets merged) — whether
that check's own text-matching heuristic is well-calibrated against
mentions of "LLM" in sentences that actually describe keeping the LLM
*out* of a decision is a separate, pre-existing question this fix did
not introduce and did not attempt to resolve.

4 new falsifiable tests (synthetic fixtures): a wrapped bulleted
question reclassifies correctly, a wrapped bullet does not swallow the
next sibling bullet, a wrapped RFC-2119 rule's exception clause is kept,
a wrapped numbered step is kept. All 757 pre-existing tests passed
UNCHANGED (no fixture needed updating) -- the join logic's stopping
rules were conservative enough not to alter any previously-correct
extraction. Full suite green at 765 tests.

# SCOPE_TRIGGER_MISMATCH audit: 81% is a blind-spot bug, 19% is the check's own stated limitation

**Date:** 2026-10-02
**Context:** continuation of the same-session sweep of large CANDIDATE
classes (after DESCRIPTION_BODY_GAP/ADR-0019, NON_DETERMINISTIC_
INSTRUCTION, MISSING_FAILURE_MODE). 54 hits on mukul975/Anthropic-
Cybersecurity-Skills.

## What the check does

`_check_scope_trigger_mismatch` (`auditor.py:819`) tokenizes the skill's
declared trigger (from the description) and compares it to the tokens of
the skill's `rules` **only**. If the two sets share zero tokens, it fires.
`procedural_steps`, `checks`, and `body_text` are never consulted.

## Measurement

For each of the 54 flagged skills, recomputed the trigger/content overlap
against `procedural_steps` and `checks` as well as `rules`:

| Signal that resolves it | Count | Share |
|---|---|---|
| `procedural_steps` tokens overlap the trigger | 42 | 78% |
| `checks` tokens overlap the trigger (steps didn't) | 2 | 4% |
| Neither resolves it; even the full `body_text` shares zero tokens with the trigger | 10 | 19% |

**81% (44/54) is the same blind-spot shape found in DESCRIPTION_BODY_GAP
before its ADR-0019 fix**: the check consults only one IR list (`rules`)
when a corpus that favors numbered-step methodology over RFC-2119
phrasing keeps almost all of its topical content in `procedural_steps`
instead. Verified concretely, e.g. `analyzing-windows-amcache-artifacts`:
the trigger is "Amcache forensics, program execution evidence gathering,
or application compatibility cache investigations in DFIR work"; the
skill has exactly **one** rule, about transaction-log replay mechanics
("Always collect the transaction log files... AmcacheParser replays
uncommitted transactions...") — genuinely zero lexical overlap with the
trigger. But the skill's 8 procedural steps ("Acquire the Amcache.hve
File", "Parse Amcache with AmcacheParser", ...) obviously match the
trigger's topic; the check never looks at them.

Two more spot-checks of the 42 confirmed clean, non-coincidental overlap
(not a single shared stopword slipping through):
- `building-detection-rules-with-sigma`: overlap = `{detection, sigma,
  intelligence, mitre, att&ck, logic, threat}`.
- `configuring-multi-factor-authentication-with-duo`: overlap = `{duo,
  privileged, access, mfa, logins, vpn}`.

## The remaining 19% (10/54) is the check's own already-stated limitation, not a new bug

For these 10, even the entire `body_text` shares zero tokens with the
trigger. Read in full, they are not errors: the trigger is phrased in
abstract/outcome terms ("high-fidelity intrusion detection in
low-telemetry areas... catch credential dumping and data-theft staging")
while the body is phrased in concrete tool/implementation terms
("Canarytokens-based decoy artifacts, honey credentials, DNS tokens, web-
bug URLs"). This is lexical disjointness without semantic disjointness —
exactly the limitation the check's own docstring and finding already
name explicitly ("lexical token disjointness is not semantic
disjointness... an LLM confirmation layer is deferred"). This is not a
vocabulary-list gap like the other mechanisms found this session; closing
it would require real semantic matching, which the check already defers
to the (separate, LLM-based) confirmation layer. Not a bug; CANDIDATE is
the correct and honest status for these 10.

## What this does and does not resolve

- **The `rules`-only blind spot (44/54)** is a narrow, low-risk fix:
  compare the trigger against the union of `rules`, `procedural_steps`,
  and `checks` tokens (same three IR lists DESCRIPTION_BODY_GAP already
  treats as "the skill's normative content"), not `rules` alone.
- **The remaining 10/54** should NOT be touched — they are the check
  correctly doing what it says it does, with an honestly stated
  limitation already pointing at the right long-term fix (LLM semantic
  confirmation, out of scope for this pattern-based check).

**Update, same date: fixed, on Anna's go-ahead -- with a self-caught
scope-expansion mistake along the way.**

The first implementation broadened both the *comparison* (rules+steps+
checks instead of rules alone) and the *gate* (evaluate a skill if ANY of
rules/steps/checks is non-empty, instead of requiring at least one rule).
That gate change put 51 previously-never-evaluated zero-rule skills in
scope for the first time -- mukul975's count went 54 -> **61**, the
opposite of the intended direction. Diffing the before/after skill sets
caught this immediately: spot-checking `analyzing-api-gateway-access-
logs` (0 rules, 5 steps, trigger "investigating API abuse or building
API-specific threat detection rules") showed its steps alone ("BOLA/IDOR:
sequential resource ID enumeration") share nothing with the trigger, but
`body_text` does (`{detection, threat, building, rules, investigating,
api}`) -- the same root cause (too narrow a text slice) one level down,
and out of scope for what was measured and reported.

Fixed by keeping the original gate (skip a skill with zero rules --
unchanged population) and broadening only the *comparison* for skills
already in scope. Re-verified:

| Corpus | Before | After | Removed | Added |
|---|---|---|---|---|
| mukul975 | 54 | 10 | 44 | 0 |
| Author's own corpus | 18 (not 0 -- an earlier assumption in this session was wrong, corrected here) | 2 | 16 | 0 |

The 10 (mukul975) and 2 (author corpus) remaining are the same already-
accepted lexical-vs-semantic limitation, not new findings. 3 new
regression tests (steps-only match, checks-only match, genuine mismatch
across all three still fires). Full suite and mutation gate green.

**Lesson for next time**: a fix that changes a check's *gate* (which
skills are even evaluated), not just its *comparison*, needs its own
before/after skill-set diff -- re-running against only the originally-
flagged skills is not enough to catch a scope expansion that creates
brand-new findings elsewhere.

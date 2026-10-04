# OVERCLAIM audit: quoted-phrase and embedded-clause blindness, both fixed

**Date:** 2026-10-04
**Context:** continuation of the systematic L2-check held-out audit.
5 hits on the held-out corpora (sports-skills 1, terminalskills 4).

## Read all 5 in full. Two mechanisms, both narrow

The check already exempts a rule's own overall `ALWAYS`/`NEVER`
modality from the `always`/`never` patterns (that word IS the
modality, not a descriptive overclaim) -- but every one of these 5
hits slipped past that existing exemption through a gap it didn't
cover.

### Mechanism A: embedded clause, rule's overall modality is something else (4/5)

- `kubernetes-helm` (modality IMPERATIVE): "Pin image tags — **never**
  use `latest` in production."
- `pdf-merge-split` (modality IMPERATIVE): "Preserve the original
  files. **Never** modify input PDFs in place."
- `envoy` (modality IMPERATIVE): "...distroless ones `distroless-
  v1.39.2`. **Always** validate a file before starting or deploying
  it:"
- `ubiquitous-language` (modality MUST_NOT): "Do not rename code
  silently..., and **never** rename persisted or public names...
  without a migration plan."

In each, the rule's own overall modality (set from its FIRST clause --
"Pin", "Preserve", "Pin an exact tag", "Do not rename") is IMPERATIVE
or MUST_NOT, not ALWAYS/NEVER, so the existing rule-level exemption
never applies. But the embedded "Always"/"Never" clause partway
through the rule is itself a second normative instruction (there is
nothing to validate before deploying; there is nothing wrong with
modifying PDFs), not a claim about absolute reliability.

### Mechanism B: overclaim vocabulary named inside a quoted phrase (1/5)

`sports-skills/world-cup` (modality NEVER, already exempts "never"
itself): '**Never** use "**guaranteed** edge", "guaranteed profit", or
"bet this" language.' The rule's own "never" is correctly exempted by
the existing logic, but "guaranteed" -- a *different* pattern -- still
matched, even though it only appears inside a quoted banned-phrase
list. The rule prohibits *using the phrase* "guaranteed edge"; it does
not itself claim anything is guaranteed.

## What was fixed, on Anna's go-ahead

Before matching, strip two spans from a working copy of the rule text
(the original `text` is kept, unchanged, for the finding's evidence):

- `_QUOTED_SPAN` removes any `"..."` or `` `...` `` span, so quoted/
  backticked vocabulary is never asserted, only possibly prohibited.
- `_CLAUSE_INITIAL_ALWAYS_NEVER` removes an "Always"/"Never" that
  starts a clause (text start, or right after `.`/`;`/`:`/an em-dash,
  or `, and `) -- the same reasoning the existing modality-level
  exemption already uses, generalized to any clause in the rule, not
  only its first one.

3 new tests: the quoted-phrase case, the embedded-clause case, and a
negative control proving "always" used as a genuine mid-sentence
adverb ("...and it always succeeds under every condition") still
fires -- the clause-initial exemption must not swallow a real
overclaim.

Verified by diffing skill+rule-id sets, not just counting:

| Corpus | Before | After | Removed | Added |
|---|---|---|---|---|
| microsoft-skills | 0 | 0 | 0 | 0 |
| sports-skills | 1 | 0 | 1 | 0 |
| terminalskills | 4 | 0 | 4 | 0 |
| mukul975 | 1 | 1 | 0 | 0 |
| Author's own corpus | 9 | 7 | 2 | 0 |

All 5 held-out hits resolved; 2 more resolved in the author's own
corpus (the same mechanism recurs there too, confirming it generalizes
beyond this one held-out sample). Zero new findings anywhere. Full
suite and mutation gate green.

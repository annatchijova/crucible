# MISSING_FAILURE_MODE audit: mostly well-calibrated, two fixable extraction bugs

**Date:** 2026-10-02
**Context:** continuation of the same-session sweep of large CANDIDATE
classes after DESCRIPTION_BODY_GAP (ADR-0019) and NON_DETERMINISTIC_
INSTRUCTION were fully classified. 61 hits on mukul975/Anthropic-
Cybersecurity-Skills.

## Result: NOT a 100% false-positive check, unlike the other two

20/61 (33%) are false positives from two concrete, narrow extraction bugs.
The remaining 41/61 (67%) were spot-checked (8 random, plus the earlier
ones read in full) and are genuine true positives: substantial,
well-structured skills (procedural steps, verification/validation
sections) that contain, by any reasonable reading, zero discussion of
what happens when the procedure fails. `MISSING_FAILURE_MODE` is a
meaningfully different case from DESCRIPTION_BODY_GAP and
NON_DETERMINISTIC_INSTRUCTION's 100% false-positive rates — this check is
largely doing its job.

## Mechanism 1: verb conjugation gap (15/61, 25%)

`_FAILURE_MODE_PATTERNS` in `auditor.py` matches `fail`, `failed`,
`failure`, `error`, `exception`, `fallback`, `recover`/`recovery`,
`rollback`, `abort`, `timeout`, `degrade`/`degradation` — but every one of
these is anchored `\bWORD\b` or `\bWORD(?:suffix)?\b` with a suffix list
that omits the plain `-s` (third person singular / plural) and `-ing`
forms. `fails`, `failing`, `errors`, `exceptions`, `fallbacks`,
`recovers`/`recovering`, `rollbacks`, `aborts`/`aborting`, `timeouts`,
`degrades`/`degrading` all fail to match. Confirmed directly:

```python
>>> re.search(r"\bfail(?:ed|ure)?\b", "fails", re.I)
None
```

The check's own two-word pattern
(`\bif\s+(?:it|this|the)\s+(?:fails?|errors?)\b`) already uses `fails?`
with the `?` — proof the author was aware of this conjugation and simply
didn't propagate it to the main single-word pattern. Same shape as the
two compiler-bugs found earlier this session (two things meant to encode
one concept, one updated, the other not) — a third instance of that
pattern, as flagged as worth checking for in
`docs/evidence/2026-10-02-mukul975-corpus-audit/FINDINGS.md`.

15 skills resolve once the conjugations are added. Spot-checked 4 for
genuineness (not a broadening artifact):

- `implementing-aes-encryption-for-data-at-rest`: "Decryption **recovers**
  original plaintext exactly" (a verification checklist item).
- `performing-binary-exploitation-analysis`: "Test that the exploit
  **fails** gracefully when mitigations are re-enabled."
- `scanning-infrastructure-with-nessus`: "**Failing** to tune plugins
  leading to excessive false positives" — inside a Pitfalls-style list.
- `securing-aws-iam-permissions`: "**Failing** to check all three accounts
  for unauthorized activity leaves potential backdoors undetected" —
  inside an explicit `**Pitfalls**:` paragraph.

All four are genuine discussions of failure/recovery; none is a spurious
match on an unrelated word.

## Mechanism 2: a "Common Pitfalls" section is failure-mode content with none of the check's vocabulary (5/61, 8%)

5 more skills have a `## Common Pitfalls` (or equivalent) section whose
bullets describe failure modes entirely in domain-specific phrasing
("Using implicit grant instead of authorization code + PKCE", "Not
validating state parameter enabling CSRF attacks") with zero occurrence
of fail/error/exception/fallback/recover/rollback/abort/timeout/degrade
anywhere in the section. The check has no heading-based signal at all
(unlike the fix just made to DESCRIPTION_BODY_GAP) — it only ever looks
at the combined text for specific words.

Verified the heading exists and is genuine failure-mode content in all 5:
`configuring-oauth2-authorization-flow`, `implementing-continuous-
security-validation-with-bas`, `implementing-pci-dss-compliance-
controls`, `managing-intelligence-lifecycle`, `performing-asset-
criticality-scoring-for-vulns`.

## What this does and does not resolve

- **Mechanism 1 (conjugation)** is a narrow, low-risk fix: broaden the
  suffix alternation on the existing patterns (`fail` -> add `s`/`ing`;
  same for `error`, `exception`, `fallback`, `recover`, `rollback`,
  `abort`, `timeout`, `degrad`). No new false negatives expected — these
  are strictly more permissive versions of patterns already in the list.
- **Mechanism 2 (Pitfalls heading)** is a second, separately-scoped
  signal: detect a heading matching `(common\s+)?(pitfalls?|
  troubleshooting|known\s+issues?|limitations?|failure\s+modes?)` and
  treat its presence as satisfying the failure-mode requirement, the
  same shape as DESCRIPTION_BODY_GAP's `structural_headings` fix. Lower
  risk than it looks: a heading titled "Pitfalls"/"Troubleshooting"/etc.
  is, by construction, about failure, so false-negative risk from this
  specific heading list is low -- but it is still a new boilerplate-
  style exclusion/inclusion list, the kind of thing ADR-0019 flagged as
  needing explicit commitment rather than silent inference.
- **The remaining 41/61** are not addressed by either fix and, on
  sampling, should not be -- they are the check working as intended.

**Update, same date: both mechanisms fixed, on Anna's go-ahead.**
`_FAILURE_MODE_PATTERNS`'s suffix alternations now include `-s`/`-ing`
(and `-ed` where missing) for every base word, and a new
`_FAILURE_MODE_HEADING` pattern (`auditor.py`) matches a
`(Common )?Pitfalls/Troubleshooting/Known Issues/Limitations/Failure
Modes` heading in the skill's body text; `_check_missing_failure_mode`
suppresses the finding on either signal. Verified against the real
corpus:

| Corpus | Before | After |
|---|---|---|
| mukul975 | 61 | 41 (exactly the predicted 20-skill drop: 15 conjugation + 5 heading) |
| Author's own corpus | 0 | 0 (unaffected, as expected) |

6 new regression tests in `test_engineering_checks_contract.py`,
including a negative control proving an unrelated heading does not
suppress a genuine positive. Full suite and mutation gate green.

# REQUIREMENT_WITHOUT_CHECK audit: one clean fix, one deferred ambiguity, mostly genuine

**Date:** 2026-10-02
**Context:** final check in the same-session sweep (after DESCRIPTION_BODY_GAP,
NON_DETERMINISTIC_INSTRUCTION, MISSING_FAILURE_MODE, SCOPE_TRIGGER_MISMATCH,
CHECK_WITHOUT_ORACLE). 34 hits on mukul975/Anthropic-Cybersecurity-Skills
(already down from 70 earlier this session via the ADR-0015 verb-list-drift
fix — this audit is of the 34 that remained).

## What the check does

`_check_requirement_without_check` (`auditor.py:261`) fires when a skill
has at least one normative rule but zero entries in `skill["checks"]`.
`checks` is populated by `_extract_checks` (`compiler.py:974`), which only
looks in sections whose title contains the literal substring `"check"` or
`"verification"`, plus any body line starting with a verification verb.

## Mechanism A: the "Validation Criteria" section-title gap (11/34, 32%)

Same bug shape as ADR-0019's original `_PROCEDURAL_SECTIONS` gap (missing
the singular "step"): `_extract_checks`'s section filter
(`if "check" not in title and "verification" not in title: continue`)
never matches "Validation Criteria" or "Validation" — a section-heading
convention this corpus uses constantly and that this very session's first
finding (DESCRIPTION_BODY_GAP) already mentioned in passing ("a
Validation Criteria section with 7 checks"), without this check having
been revisited since.

Verified: `implementing-aes-encryption-for-data-at-rest` has a `##
Validation Criteria` section with 7 real checkbox items ("AES-256-GCM
encryption produces valid ciphertext", "Nonces are never reused for the
same key", ...), entirely invisible to `_extract_checks`. Spot-checked 2
more (`configuring-hsm-for-key-storage`, `performing-ssl-certificate-
lifecycle-management`) — both have a genuine `## Validation Criteria`
checkbox list, same shape.

11/34 skills have a `## Validation`, `## Validation Criteria`, or `##
Validation and Testing` heading (checked with the compiler's own
code-fence-aware heading extraction, not a raw-text scan — a raw scan
produced several false leads that turned out to be shell comments inside
code fences, e.g. `# Verify database connection` after `msfconsole -q` in
a bash block, already correctly excluded by this session's earlier
code-fence fix).

## Mechanism B: a Step-N heading with a verification verb in its title (4/34, 12%) — deferred, not fixed

- `exploiting-vulnerabilities-with-metasploit-framework`: "Step 2:
  Validate Specific Vulnerabilities"
- `implementing-network-segmentation-for-ot`: "Step 3: Validate
  Segmentation Effectiveness"
- `implementing-rbac-hardening-for-kubernetes`: "Step 3: Check Default
  Service Account Usage", "Step 4: Verify Token Auto-Mount"
- `implementing-runtime-security-with-tetragon`: "Step 3: Verify
  Installation"

These steps DO contain verification activity, but as a procedural step
(ADR-0019 B.1's own Step-N extraction correctly captures them as steps),
not as a checklist item with an oracle. Treating any step whose heading
contains a verification verb as also satisfying "has a check" is the same
shape of risk as CHECK_WITHOUT_ORACLE's deferred mechanism C: it would
blur the rule/step/check distinction this session already fixed one
confirmed over-classification bug for (ADR-0015, 250/818 skills affected).
Left as an open question, not implemented.

## The remaining 19/34 (56%): genuine true positives

Spot-checked 3 in full (`exploiting-zerologon-vulnerability-cve-2020-1472`,
`implementing-hipaa-security-rule-safeguards`,
`deobfuscating-javascript-malware`): zero lines anywhere in the body
start with a verification verb, and no Checks/Verification/Validation-
style section exists at all. These skills follow a different template
(ending in `Key Concepts` / `Tools & Systems` / `Common Scenarios` /
`Output Format`, used by a visible cluster within this corpus) that
simply never states how to verify its one rule. Correctly CANDIDATE.

## What this does and does not resolve

- **Mechanism A**: narrow, low-risk fix — add "validation" to
  `_extract_checks`'s section-title filter, mirroring exactly how
  `_check_description_body_gap`'s own boilerplate-exclusion precedent
  already treats this corpus's section-naming conventions as a committed,
  named list rather than an inferred one.
- **Mechanism B**: deferred — a real ambiguity about whether a
  verification-flavored step title should count as a check, not a
  vocabulary-list patch.
- **Mechanism D-equivalent (19/34)**: untouched, correctly CANDIDATE.

**Update, same date: mechanism A fixed, on Anna's go-ahead.**

`_extract_checks`'s section-title filter now also matches "validation"
(so "Validation Criteria"/"Validation"/"Validation and Testing" are
recognized alongside "Checks"/"Verification"). Verified by diffing skill
sets:

| Corpus | Before | After | Removed | Added |
|---|---|---|---|---|
| mukul975 | 34 | 24 | 10 | 0 |
| Author's own corpus | 13 | 13 | 0 | 0 (doesn't use this heading convention) |

10, not the 11 predicted: `implementing-next-generation-firewall-with-
palo-alto`'s "## Validation and Testing" section uses a **numbered**
list (`1. **Policy Audit** - ...`), not bullets -- `_extract_checks`'s
section-content loop only ever matched `_BULLET`, never `_NUMBERED`, so
numbered items inside a Checks/Verification/Validation section were
already invisible before this fix too (true for "## Checks" sections as
well, this just makes the gap visible for the first time on a skill
whose heading now passes the filter). This is a real, separate,
pre-existing limitation, out of scope for what was measured and
approved here -- left as a documented residual, not fixed. 3 new
regression tests (Validation Criteria extraction at the compiler level,
end-to-end suppression, and a negative control for an unrelated
heading). Full suite and mutation gate green.

Mechanism B (Step-N heading with a verification verb) remains deferred.
The 19/34-equivalent true positives remain untouched.

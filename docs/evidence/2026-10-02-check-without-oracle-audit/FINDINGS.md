# CHECK_WITHOUT_ORACLE audit: two narrow fixes, one real open design question

**Date:** 2026-10-02
**Context:** continuation of the same-session sweep (after DESCRIPTION_BODY_GAP,
NON_DETERMINISTIC_INSTRUCTION, MISSING_FAILURE_MODE, SCOPE_TRIGGER_MISMATCH).
27 hits on mukul975/Anthropic-Cybersecurity-Skills (already down from 91
earlier this session via the ADR-0015 verb-list-drift fix — this audit is
of the 27 that remained after that fix).

## What the check does

`_extract_oracle_kind` (`compiler.py:1049`) classifies a check's text as
"question" (ends in `?`), "checkbox" (`[ ]`/`[x]`), "command" (contains
one of `_VERIFICATION_VERBS`: verify/assert/run/check/confirm/test/query/
inspect/does/ensure/prove/validate/demonstrate, searched anywhere via
`\bVERB\b`), or "unknown". `CHECK_WITHOUT_ORACLE` fires on "unknown".

## Read all 27 in full. Four distinct buckets.

### Mechanism A: verb conjugation (5/27) — same bug shape as the session's 3 prior instances

`\b(?:verify|...|validate|...)\b` matches "validate" but not "validates"
— same conjugation gap already fixed in NON_DETERMINISTIC_INSTRUCTION's
grammar pattern and MISSING_FAILURE_MODE's vocabulary this session.
Confirmed: `re.search(r"\bvalidate\b", "Validates")` is `None`. All 5
cases are from one skill's "## Checks" section written in third-person
declarative style rather than imperative:

- `implementing-api-security-testing-with-42crunch`: "**BOLA
  Prevention**: Validates that...", "**BFLA Prevention**: Checks for...",
  "**Injection Prevention**: Ensures...", "**Security Misconfiguration**:
  Checks...", "**Mass Assignment**: Validates...".

### Mechanism B: an inline runnable command is itself a command oracle, independent of the leading verb (1/27)

`performing-threat-hunting-with-yara-rules`: "Compile all custom rules
without syntax errors: `yara -w rules/*.yar /dev/null`" — contains an
actual, literal, runnable command in backticks. "Compile" is not a
verification verb, so the check never looks at the command itself. A
check whose text contains inline code (`` `...` ``) or a fenced code
block has a self-evident oracle (run it, see if it errors) regardless of
its leading verb.

### Mechanism C: configuration/mitigation imperatives under a Checks heading (13/27) — NOT a narrow fix, a real open question

"Enable Continuous Access Evaluation Protocol (CAEP)...", "Configure
critical event triggers...", "Monitor CAE event logs...", "Disable NTLM
on the CA enrollment endpoint...", "Patch coercion vectors...", etc.
(`implementing-identity-verification-for-zero-trust` x7,
`relaying-ntlm-for-adcs-esc8` x5, one more in the tabletop-exercise skill).
These are hardening/mitigation instructions living under a "Checks" or
"Validation Criteria" heading, not phrased as a verifiable test at all —
but each has an *implicit* binary state ("is CAEP enabled, yes or no?").
Adding `enable`/`disable`/`configure`/`monitor`/`implement`/`patch`/
`remove` to the oracle vocabulary is a materially different design move
than fixing a conjugation gap: those words heavily overlap `_ACTION_VERBS`
(mitigation/step vocabulary), already a source of a confirmed rule/step/
check over-classification bug fixed earlier this session (ADR-0015). This
risks reintroducing that exact problem in reverse — a mitigation-style
step misclassified as having a command oracle just because it uses an
action verb, when "enabled" is an implicit state check, not an inherent
property of the verb. This needs a real decision (what's the actual
invariant: "contains a verification verb" vs. "implies a checkable binary
state"?), not a vocabulary-list patch. Deferred.

### Mechanism D: genuine true positives — vague or deliverable-style text with no pass/fail criterion (8/27)

Read individually; none of these states anything an agent could check as
true/false:

- `analyzing-ransomware-payment-wallets`: "Cross-reference transaction
  timestamps with known incident timelines." / "Compare findings against
  OFAC SDN list for sanctioned addresses." — plausible investigative
  actions, no stated success criterion.
- `detecting-living-off-the-land-attacks`: "Cross-reference detections
  against the LOLBAS project database... for completeness." — same.
- `auditing-tls-certificate-transparency-logs`: "**Certificate inventory
  report**: Produce a complete inventory...", "**CA diversity
  analysis**: Report on how many different CAs...", "**Compliance
  evidence**: For organizations subject to PCI-DSS...". These are
  deliverables/report descriptions, not checks with a pass/fail oracle.
- `building-ransomware-playbook-with-cisa-framework`: "Conduct tabletop
  exercise using the playbook with all stakeholders." / "Review and
  update the playbook at least annually or after any incident." — tasks,
  not verifiable conditions.

Correctly left CANDIDATE. Not touched.

## What this does and does not resolve

- **Mechanism A (conjugation)**: narrow, low-risk fix — add the regular
  3rd-person/past/-ing forms for each verb to a new pattern used only by
  `_extract_oracle_kind` (NOT the shared `_VERIFICATION_VERBS` tuple,
  which `_VERIFICATION_STARTER` also uses to decide whether a bullet
  becomes a check at all — that path is almost always imperative, so
  conjugation doesn't apply there and touching the shared tuple would be
  a wider, unmeasured change).
- **Mechanism B (inline code)**: narrow, low-risk fix — add a pattern
  detecting a markdown inline code span or fenced code block anywhere in
  the check text as its own "command" signal.
- **Mechanism C (configuration imperatives)**: NOT fixed. A real design
  question about what the command-oracle invariant actually is, with a
  concrete risk of reintroducing an already-fixed classification bug if
  done carelessly. Anna's call, not an implementer default.
- **Mechanism D (8/27)**: not touched, correctly CANDIDATE.

**Update, same date: mechanisms A and B fixed, on Anna's go-ahead.**

New `_VERIFICATION_VERB_CONJUGATIONS` dict (hand-written per verb, not a
blind suffix rule -- English conjugation is irregular: "verify" ->
"verifies", not "verifys"; "run" -> "running", not "runing") feeds a new
`_ORACLE_VERB_ALTERNATION` used only by `_extract_oracle_kind`, leaving
the shared `_VERIFICATION_VERBS` tuple (and `_VERIFICATION_STARTER`,
which only ever sees imperative bullets) untouched. A new
`_ORACLE_INLINE_CODE` pattern (any backtick span) adds a second signal
for mechanism B.

Verified against the real corpus, diffing skill sets (not just counts,
after SCOPE_TRIGGER_MISMATCH's gate-change lesson earlier this session):

| Corpus | Before | After | Removed | Added |
|---|---|---|---|---|
| mukul975 | 27 | 20 | 7 | 0 |
| Author's own corpus | 16 | 9 | 7 | 0 |

mukul975 resolved 1 more than the 6 predicted above (5 mechanism-A + 1
mechanism-B): the 6th `implementing-api-security-testing-with-42crunch`
check ("**Data Exposure**: Verifies response schemas...") was
miscounted as unresolved in the initial measurement, which used a quick
blind-suffix regex that itself has the "verify"->"verifies" irregularity
bug -- the final hand-written conjugation list handles it correctly.
Zero new findings appeared anywhere, confirming the fix is additive
(catches more real command oracles) and not overbroad.

3 new regression tests (conjugated-verb classification, inline-code
classification, and an explicit note on the inline-code pattern's real
scope — any backtick span, not just a recognizably executable one,
accepted as correct since a backticked file/config name still names a
concretely inspectable condition). Full suite and mutation gate green.

Mechanism C (configuration/mitigation imperatives) remains an open design
question, untouched. Mechanism D (8/27 genuine true positives) untouched.

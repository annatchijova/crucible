# NON_DETERMINISTIC_INSTRUCTION: full classification across three corpora

**Date:** 2026-10-02
**Trigger:** Anna shared `github.com/eli-l/okf-builder` (README) as an
unrelated repo link. Its `SKILL.md` was pulled in as a third test corpus
(same role as mukul975's corpus — an external artifact to compile/audit,
not a dependency of Crucible). Compiling it against the current checks
surfaced a `NON_DETERMINISTIC_INSTRUCTION` CANDIDATE finding that, on
direct reading, was a false positive. That single observation is what
motivated the full classification below.

## What the check does

`_check_non_deterministic` in `src/crucible/auditor.py` (~line 1510) scans
every rule's and procedural step's text for the five patterns in
`_NON_DETERMINISTIC_PATTERNS` (`random(?:ly)?`, `arbitrary`,
`pick\s+(?:any|one|a)`, `choose\s+(?:any|one|a)`,
`any\s+(?:order|way|approach|method)`), and fires unless a deterministic
anchor pattern (`seed`, `fixed`, `pinned`, `deterministic`,
`reproducib(?:le|ility)`, `same\s+(?:input|result|output)`) is also present
in the same text. No other context — modality, surrounding sentence,
domain — is consulted.

## Method

For each corpus, every `NON_DETERMINISTIC_INSTRUCTION` finding was read in
full (not sampled) against the live extracted text, cross-checked against
the raw `SKILL.md` where the extractor truncated at a step/rule boundary.
Each was classified as a genuine methodology defect (TRUE) or a false
positive, and every false positive was assigned to one of eight observed
mechanisms.

## Results

| Corpus | Flagged | False positives | True positives |
|---|---|---|---|
| okf-builder (`eli-l/okf-builder`, 1 skill) | 1 | 1 | 0 |
| mukul975/Anthropic-Cybersecurity-Skills (818 skills) | 19 | 19 | 0 |
| Author's own corpus (`~/SKILLS`) | 3 | 3 | 0 |
| **Total** | **23** | **23 (100%)** | **0** |

Zero genuine true positives found across three independently-written
corpora, one of which (the author's own) is presumably closest to the
style the check was designed against. This is a stronger result than
DESCRIPTION_BODY_GAP's 177/177 — that one was corpus-specific (a style
mismatch with one external author); this one reproduces at 100% in the
author's own skills too.

## The eight false-positive mechanisms

### 1. Domain-correct required randomness (crypto/security primitives)

The flagged text describes randomness that is the *correct, mandatory*
property of a security primitive. Pinning or seeding it, which is exactly
what the deterministic-anchor vocabulary would encourage, would introduce
a real vulnerability — nonce reuse, a predictable PKCE verifier, a
non-random ZK challenge.

- `configuring-oauth2-authorization-flow` step-0005/step-0010: "Client
  generates random `code_verifier`" / "Generate cryptographically random
  code_verifier (min 43 chars)" — PKCE (RFC 7636) requires this.
- `implementing-aes-encryption-for-data-at-rest` step-0003: "Create a
  random nonce for each encryption operation" — AES-GCM nonce reuse is a
  known catastrophic failure.
- `implementing-zero-knowledge-proof-for-authentication` step-0003/0004:
  "Prover sends t = g^r mod p (random r)" / "Verifier sends random c" —
  Schnorr/Fiat-Shamir protocol correctness requires both.
- `exploiting-kerberoasting-with-impacket` step-0001: "Use gMSA — 240-
  character random passwords, auto-rotated" — the random+rotation *is* the
  mitigation being recommended.
- `performing-api-rate-limiting-bypass` step-0005: "Adding `?_=<random>`
  to each request bypasses the rate limit" — the random value is a
  cache-buster probe; its exact value is immaterial to the test's
  reproducibility (the *outcome* — bypass succeeds or not — is what must
  reproduce, and does).
- Author's own `diagnosing-bugs` step-0011: "run 1000 random inputs and
  look for the failure mode" — this is a fuzz/property-test loop; random
  input generation is the defining mechanism of fuzzing, not a
  reproducibility defect in the methodology.

### 2. Descriptive text about attacker/adversary capability (not an instruction to the agent at all)

The text explains what an attacker, malware, or vulnerability *can do* —
third-person description of a threat, not a second-person instruction
telling the agent to act randomly or arbitrarily.

- `detecting-golden-ticket-attacks-in-kerberos-logs` step-0004: "Golden
  Tickets can include arbitrary SIDs."
- `detecting-t1548-abuse-elevation-control-mechanism` step-0009: "sdclt.exe
  Bypass: Leveraging... auto-elevation to execute arbitrary commands."
- `escaping-containers-to-host` step-0004 (CVE-2025-31133 family): "...
  allowing read-write access to `/proc` entries... and arbitrary write
  redirection."
- `exploiting-prototype-pollution-in-javascript` step-0002: "Exploit
  EJS/Pug/Handlebars gadgets to execute arbitrary commands."
- `hunting-for-command-and-control-beaconing` step-0011: "DGA-based C2:
  Malware generating random domains daily."
- `testing-for-json-web-token-vulnerabilities` step-0002/0004: "forge
  arbitrary tokens for administrative access" / "forge arbitrary JWTs for
  any user" — describing what a successful attack achieves.
- Author's own `data-leakage-hunting` step-0005: "Temporal leakage. A
  random split on time-series data..." — this is the *anti-pattern being
  warned against*, an example of a mistake to avoid, not an instruction to
  perform a random split.

This is the largest single bucket: 7 of 19 mukul975 findings, plus 1 of 3
author-corpus findings.

### 3. "Any order"/"any X" as a vulnerability description of record-level access, not a sequencing instruction

The `any\s+(?:order|way|approach|method)` pattern was written for "do the
steps in any order" (an ordering/sequence claim). In security-audit text
about e-commerce or object-level authorization bugs, "order" is a noun for
a purchase record, and "any order" describes *which records* are
reachable (the vulnerability), not a claim about sequencing.

- `performing-web-application-penetration-test` step-0003: "any
  authenticated user can view any order by iterating order ID" (IDOR).
- `testing-api-for-broken-object-level-authorization` step-0014: "returns
  any order regardless of ownership (BOLA on read)."

### 4. Proper-noun / terminology collision

"Random" is a substring of a named algorithm, not the adjective describing
non-determinism.

- `detecting-command-and-control-over-dns` step-0011: "Train **Random
  Forest** and Gradient Boosting classifiers" — Random Forest is a
  specific, named, deterministic-given-a-seed ML algorithm; the check has
  no way to distinguish the proper noun from the common adjective.

### 5. Meta-reference: instructing an audit of randomness in an external system

The rule tells the agent to *check* the quality of someone else's RNG — the
word "random" names the audit's *subject*, not a property of the
methodology's own execution.

- `performing-cryptographic-audit-of-application` rule-0001 (IMPERATIVE):
  "Validate random number generator usage."

### 6. "Arbitrary" as configuration flexibility, not unprincipled choice

"An arbitrary REST endpoint" means "whichever endpoint you configure" —
describing the tool's generality, not instructing the agent to behave
without a stated principle.

- `red-teaming-llms-with-garak` step-0019: "Configure garak against a local
  Hugging Face model, an OpenAI-compatible API, and an arbitrary REST
  endpoint."

### 7. Grammatical conflation: "pick a NOUN" vs. "pick any/one NOUN"

`\bpick\s+(?:any|one|a)\b` conflates the ordinary indefinite article ("pick
a `type`" = select the one that applies) with a genuinely unconstrained
choice ("pick any/one").

- `okf-builder` step-0002 (the finding that started this investigation):
  "**Pick a `type`** that matches the kind. Use self-explanatory values."
  — the sentence immediately constrains the choice to "matches the kind";
  there is nothing arbitrary about it.

### 8. Polarity blindness: a MUST_NOT rule is flagged as if it introduced what it prohibits

The check never consults the rule's own modality. A rule whose entire
content is "do not do X" is flagged as introducing X whenever X's
vocabulary (here, "arbitrary") appears in its text.

- Author's own `debt-closure-discipline` rule-0005 (modality `MUST_NOT`):
  "**MUST NOT** assign an arbitrary numeric threshold ('5 patches,' '3
  workarounds') for this judgment; it is a qualitative call." — this rule
  exists specifically to *forbid* the non-determinism the check claims it
  introduces. Of the eight mechanisms, this is the sharpest: the finding is
  not just irrelevant to the rule's intent, it is the exact inverse of it.

## Why this is not an artifact of corpus selection

The three corpora differ in author, domain, and style (a 257-line
well-structured Go-toolchain skill; 818 independently-written offensive/
defensive security skills; the author's own 97-skill forensic-methodology
corpus). All three produced 100% false positives, and five of the eight
mechanisms (1, 2, 7, 8, and arguably 6) are not corpus-specific — they
follow directly from the check's design (bare keyword matching with no
polarity, no prescriptive/descriptive distinction, no sense
disambiguation), not from any one corpus's writing style. The expectation
that a differently-styled fourth corpus would also reproduce this is a
testable prediction, not an assumption — it was not run here, since three
independent 100%-false-positive corpora already settle the question this
investigation needed to settle.

## What this does and does not resolve

This confirms the check's current form is, at minimum, badly miscalibrated
for every corpus examined so far. It does **not** by itself answer what the
fix should be — that is a design decision with the same shape as
ADR-0019's Option A/B choice, and for the same reason: the easy fixes only
cover some of the mechanisms.

- **Mechanism 8 (polarity)** is a narrow, low-risk fix: skip the check for
  a rule whose modality is in `_NEGATIVE_MODALITIES` (already defined at
  `auditor.py:599`, reused as-is). This mechanism only applies to the
  `rules` branch of the check (procedural steps carry no modality field).
- **Mechanism 7 (grammar)** is a narrow, low-risk fix: drop the bare `a`
  alternative from `\bpick\s+(?:any|one|a)\b` (and the equivalent for
  `choose`). Checked this does not lose a genuine positive: a true
  "pick a random X" is still caught by the separate `\brandom\b` pattern,
  so narrowing this one pattern loses no coverage.
- **Mechanisms 1, 2, 3, 4, 5, 6** all require distinguishing a prescriptive
  instruction to the agent from descriptive domain text (about attackers,
  about an external system's RNG, about a named algorithm, about record
  identifiers, about tool configurability). The L1 IR does not currently
  carry any signal for "is this text addressed to the agent as an action"
  vs. "is this text explaining the domain" — building that signal reliably
  is a real design problem, not a word-list patch, and it is exactly the
  kind of question ADR-0019 was written to make explicit rather than
  resolve ad hoc inside a keyword list.

**Update, same date: mechanisms 7 and 8 fixed, on Anna's go-ahead.**
`_NON_DETERMINISTIC_PATTERNS`'s `pick`/`choose` alternation dropped the
bare `a` (mechanism 7), and `_check_non_deterministic`'s rule loop now
skips any rule whose `modality` is in `_NEGATIVE_MODALITIES` before
pattern-matching (mechanism 8, reusing the constant already defined at
`auditor.py:599`). Verified by re-running all three corpora after the fix:

| Corpus | Before | After |
|---|---|---|
| okf-builder | 1 | 0 |
| mukul975 | 19 | 19 (unchanged — none of its 19 cases were mechanism 7/8) |
| Author's own corpus | 3 | 1 (`debt-closure-discipline` resolved; `data-leakage-hunting` and `diagnosing-bugs` remain — mechanisms 2 and 1, not targeted by this fix) |

4 new regression tests added to `test_engineering_checks_contract.py`:
positive/negative pairs for both the narrowed grammar pattern and the
modality guard, confirming neither fix silently broadens into suppressing
or missing a genuine positive. Full suite (693/693) and mutation gate
(29/29) green.

Mechanisms 1-6 (the descriptive-vs-prescriptive distinction) remain open
and undecided — no code changed for those. Per the same discipline as
ADR-0019, that direction is Anna's call, not an implementer default.

## Evidence files

- `mukul975_findings.json` — all 19 mukul975 findings with skill, rule/step
  id, modality, and full extracted text, generated by `audit_corpus`
  against `~/crucible-corpora/mukul975-cybersecurity-skills` on this date.
- Author-corpus and okf-builder cases are quoted above verbatim from the
  live `SKILL.md` files (`~/SKILLS/<skill>/SKILL.md`,
  `~/crucible-corpora/okf-builder/SKILL.md`); not separately filed since
  there are only four of them.

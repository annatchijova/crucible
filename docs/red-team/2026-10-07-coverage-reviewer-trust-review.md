# Coverage adjudication: reviewer trust and evidence review

**Date:** 2026-10-07  **Base:** `7583a04`  **Method:** local source/config
inventory plus an ephemeral Ed25519/OpenSSL probe  **Status:** trust boundary
and review protocol proposed; no reviewer labels or production trust system
added.

## Question and threat model

Can Crucible distinguish (1) a relation claim from an authenticated review,
(2) key possession from an authorized reviewer, and (3) a text-level judgment
from an executed check? The attacker may control the relation-map bytes,
reviewer-name fields, signatures, and any public key embedded in that map. The
attacker cannot alter a separately maintained trust policy or a trusted
reviewer's private key. This last condition is necessary; without it, signatures
provide no reviewer attribution.

## Local state: no existing reviewer root of trust

- Search of `src/crucible` and tests found no reviewer identity registry,
  signing/verifying API, public-key allowlist, or adjudication workflow for
  rule-check links.
- `src/crucible/auditor.py` describes L2 as deterministic and authoritative
  within scope; `audit_corpus` accepts the IR, not reviewer identity or an
  attestation.
- `src/crucible/capture_bundle.py::oracle_identity` hashes local source/runtime
  material and explicitly says local code is trusted and this is not loaded-code
  attestation. A source digest is not an identity proof.
- The current `main` commit (`7583a04`) has Git signature status `N` (unsigned);
  `commit.gpgsign` and `gpg.format` are unset in this local configuration. Git
  author name/email therefore cannot be treated as an authenticated reviewer.
- GPG 2.4.4 is installed, but disposable key generation failed because this
  environment could not start `gpg-agent` (`No agent running`). The probe was
  rerun using OpenSSL 3.0.13; no user key or network service was used.

## Signature probe

The reproducible harness is
[`reviewer_signature_trust_prototype.py`](../evidence/reviewer_signature_trust_prototype.py).
It creates ephemeral Ed25519 keypairs under a temporary directory and removes
them on exit. Its pre-run oracle was:

1. A signature by a public key pinned in verifier configuration accepts the
   exact canonical payload.
2. A valid signature by a different, unpinned key is rejected by the pinned
   verifier.
3. Changing the source IR digest after signing is rejected.
4. If the verifier instead accepts the public key supplied with the artifact,
   the attacker's own valid signature verifies cryptographically, but the key
   is still not authorized.

Observed output:

```text
pinned_key_signature_accepted: true
untrusted_key_rejected_by_allowlist: true
self_supplied_key_signature_is_valid: true
changed_source_digest_rejected: true
identity_or_authority_proven: false
semantic_correctness_proven: false
```

All four oracle cases passed in two byte-identical runs. A negative control
added the attacker's key to the allowlist; `untrusted_key_rejected_by_allowlist`
then became false and the harness exited 1. Restoring the allowlist returned
the harness to green. The signature proves possession of the private key and
binds the signed bytes. It does not prove the key belongs to a named person, the
person is authorized to review Crucible, or the signed assessment is correct.

## Required separation of claims

Use distinct assertions; do not collapse them into a generic `ADJUDICATED`
boolean:

| Claim | Evidence that could support it | Residual limit |
|---|---|---|
| The source declared this relation | A source locator and source digest | May be false, stale, or written by an unknown actor |
| A heuristic/model proposed this relation | Tool/version, input digests, output digest, candidate IDs | Proposal is not a semantic verdict |
| A particular key signed this assessment | Valid signature over canonical, versioned bytes | Key possession only; key-to-person mapping is external |
| The signer is authorized for this review | Key fingerprint in a separately trusted role/validity policy | Trust policy can be wrong or stale; revocation/rotation matter |
| The check textually specifies a check for the rule | Versioned criterion, exact rule/check spans and rationale | Does not show the check ran or passed |
| The check was executed and passed | Bound test/run artifact with input, environment, oracle and result | Only the tested system/version/input scope is covered |

For textual assessment, a positive label should require a falsifiable,
observable pass/fail condition tied to the rule's subject, predicate, and
preconditions. A direct condition can qualify without a verification verb if
it states the relevant oracle. A command such as “run export” or “verify
signature” without a rule-matching condition is not enough by itself. If a
rule has multiple independent clauses, record partial relation at clause scope
or abstain; do not promote one linked clause to full-rule coverage. A text
review must never be rendered as proof that an external implementation passed.

## Candidate review protocol

This is a proposal for a future evidence set, not implemented policy:

1. Freeze exact IR/audit digests, rule/check IDs, their text digests, source
   spans, and `coverage-criterion/v1` before review.
2. Keep model and lexical proposals hidden from adjudicators until their labels
   are frozen, to reduce anchoring. Give each reviewer the original context,
   not only extracted snippets.
3. Have two reviewers assess independently at `TEXTUAL_SPECIFICATION` scope
   with outcomes `COVERS`, `PARTIAL`, `DOES_NOT_COVER`, or `UNRESOLVED`, plus
   rule clauses, observable oracle, preconditions, evidence spans, and rationale.
4. Preserve both initial assessments. Agreement on the same outcome can be a
   reviewed label for this criterion; disagreement remains unresolved unless a
   third authorized adjudicator records a separate, signed resolution. Do not
   discard disagreement counts when reporting results.
5. Report raw agreement and disagreements, and report accuracy only against a
   separately held-out set. Repeatedly tuning on the same fixture set consumes
   it. An LLM pass is corroboration, not an independent human review.
6. Keep execution evidence in a separate scope/artifact. A signature over
   prose never turns a described check into a test run.

Each reviewer statement could bind the two source digests, criterion version,
assessment scope, exact IDs/text digests, outcome, evidence locators, rationale,
and key fingerprint. Sign canonical bytes, reject duplicate JSON keys at parse
time, and keep the trusted fingerprint-to-role policy outside the map. Never
accept an artifact-supplied key as its own trust anchor.

## Trust mechanism choice

For map records stored in this Git repository, evaluate verified Git commit
signatures first: they avoid creating a second serialization/signature format.
They are useful only if the signer fingerprint is pinned outside the commit,
the signing key is provisioned and revocable, and repository policy requires
verification for the adjudication path. Those conditions are not present in
the local checkout: recent commits are unsigned and no signing format is
configured. A detached signature gives finer-grained portability but adds
canonicalization, parser, key lifecycle, and verifier dependencies. The probe
does not justify implementing either option yet.

HMAC is unsuitable for individual reviewer attribution because shared-key
holders can produce indistinguishable attestations. A digest alone detects
accidental mismatch only when the expected digest comes from a trusted channel.
Signing with a key included in the same untrusted map only proves self-asserted
key possession.

## Disposition and next falsifier

**CODE/CONFIG FACT:** this checkout has no reviewer trust root; current Git
history is not signed. **RUNTIME-CONFIRMED:** OpenSSL's pinned-key flow accepts
the pinned signature and rejects an untrusted key and modified payload under
the ephemeral test setup. **Not established:** the key belongs to a human,
reviewers are authorized, any check covers its rule, or any check was executed.

Keep `ADJUDICATED` unavailable in the coverage-map prototype. The next design
gate is to select and provision the external key-to-role trust policy and to
obtain independently adjudicated fixture labels. Reopen the Git-signing option
only after verifying real signed commits against an independently trusted
fingerprint and an enforced repository policy. Reopen the coverage claim only
after reviewers apply the written criterion while blinded to model/heuristic
proposals. No production code or schema changed in this review.

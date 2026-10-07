# Coverage relation artifact: authority boundary review

**Date:** 2026-10-07  **Base:** `eaeec72`  **Method:** source trace plus a
focused recommendation-contract test and negative-control mutation  **Status:**
architecture constraint identified; no production change or new relation
artifact adopted.

## Threat model and question

Skill Markdown and any relation map are author-controlled inputs. The model,
if used to propose links, is an untrusted source of observations. Crucible's
L1/L2 implementation and signing/digest code are assumed unchanged. The
question is whether an additive rule-check artifact can supply useful evidence
without silently replacing the L2 audit or letting stale, forged, ambiguous,
or unresolved relations change a recommendation.

## Predictions recorded before the focused run

1. `audit_corpus` should derive L2 only from the IR and expose no input for a
   relation map. If a map changes native L2 findings, this prediction is
   falsified.
2. An existing downstream artifact may affect a recommendation only through
   an explicit consumer and source-audit binding. A mismatched source digest
   should not let its candidate verdict alter the recommendation.
3. A digest and a `status: ADJUDICATED` field can establish byte integrity and
   declared state, but cannot establish who reviewed the relation or whether
   that reviewer was authorized.

## Source trace

- **L2 boundary:** `src/crucible/auditor.py` exposes
  `audit_corpus(artifact)`, reads the `skill-ir/v1` artifact, computes findings,
  and digests its own `crucible-audit/v1` payload. It takes no relation-map
  argument. Its module contract says it is the authority for findings within
  its scope.
- **Existing separate evidence path:** `src/crucible/confirm.py` emits a
  distinct confirmation artifact bound to `source_audit_digest` and
  `source_ir_digest`.
- **Explicit downstream consumer:** `src/crucible/recommendation.py` consumes
  audit plus confirmation, records a confirmation digest mismatch, and ignores
  mismatched confirmation verdicts for candidate findings. This means L2 is
  immutable while a separately versioned downstream recommendation can still
  consume separately sourced evidence. Thus “any secondary evidence is a
  second audit authority” is too broad; the concrete authority depends on the
  consumer and the claim it emits.
- **Sealed outputs:** `src/crucible/final_report.py` binds audit,
  confirmation, and recommendation digests into `crucible-final-report/v1`.
  A future coverage input would change downstream decisions and must be named
  and digested in an explicitly versioned contract; omitting it would make the
  report's provenance incomplete.

## Experiment and negative control

Ran the existing focused contract:

```text
.venv/bin/python -m pytest -q \
  tests/test_recommendation_contract.py::test_confirmation_from_a_different_audit_is_not_trusted
1 passed
```

Then temporarily disabled the mismatch guard in `recommendation.py` as a
negative control. The same test failed as expected: a `CONFIRMED` verdict
bound to `sha256:stale` changed the result from `NEEDS_CONFIRMATION` to
`MODIFY`. The original file was restored from a `/tmp` copy and the test passed
again. No mutation remains in the worktree.

This run confirms that the existing source-digest mismatch control is exercised
by the contract test. It does **not** validate any proposed coverage map,
because no such artifact or consumer exists yet.

## Red-team cases for a future coverage artifact

| Input attack / failure | Required deterministic handling | What this does not prove |
|---|---|---|
| Map references another IR or audit digest | Reject or mark unusable; never apply its relation states | A matching digest does not authenticate a human reviewer |
| Invented or stale rule/check ID | Reject the affected artifact or relation; validate IDs against the bound IR | Existing generated IDs may be unstable across unrelated source edits |
| Two conflicting states for the same rule/check pair | Reject conflict; do not let ordering choose | The conflict policy cannot decide semantic adequacy |
| `ADJUDICATED` string with no authenticated provenance | Treat as an untrusted declaration, not adjudication | A self-reported reviewer name is not authentication |
| `PROPOSED` or `DECLARED` relation interpreted as verified coverage | Keep it unresolved in the recommendation | Stronger wording in prose does not strengthen evidence |
| Relation input changes but report digest omits its digest | Fail the provenance contract | A correct digest still seals a wrong relation perfectly |
| Link map directly edits or filters L2 findings | Reject this integration shape | L2's structural finding may itself be incomplete within its stated scope |

## Disposition

**Falsified in its broad form:** a separate evidence artifact is not inherently
a second L2 authority; Crucible already has a separate confirmation artifact
that can feed a distinct L15 recommendation while preserving L2. **Still open:**
a coverage artifact would introduce a new decision input and possibly a new
coverage recommendation. The system must state whether that output is (a) a
candidate/review aid, or (b) an adjudicated recommendation. A model proposal
may support (a), not establish (b). For (b), the reviewer's identity and
authority need a real trust mechanism; a JSON status field and digest are
insufficient.

No L1/L2 schema or production code changed. No independent human adjudication
was available, so the relation correctness question remains open. The focused
test is a precedent test for stale-source handling, not a coverage-link
accuracy result.

## Next step

Draft a versioned artifact contract and validator **without wiring it into
recommendations**. Red-team the schema/ID/digest/provenance boundary first.
Only after a separate reviewer supplies fresh adjudications should a consumer
be proposed; then version the recommendation/report contract and replay its
downstream digests and behavior.

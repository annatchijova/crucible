# Red-team finding: stale status for semantic-redundancy confirmation

**Date:** 2026-10-07  
**Disposition:** fixed in this branch  
**Security classification:** documentation and evidence-quality defect; no security impact demonstrated

## Finding

At the branch base (`a7c115a`), the `SEMANTIC_REDUNDANCY` detector's source
docstring and emitted `limitation` described its executor-confirmation layer as
deferred. The public roadmap repeated that statement. The implementation already
had an optional L2.5 path that records executor output in a separate artifact.

This wording could lead a reader of a new audit artifact or the roadmap to believe
that the confirmation path did not exist. The underlying lexical comparison was
still correctly presented as a candidate signal, not semantic proof.

## Evidence and provenance

- **CODE FACT:** [`src/crucible/confirm.py`](../../../src/crucible/confirm.py)
  implements `confirm_semantic_redundancy`; it selects `CANDIDATE` findings and
  builds a separate confirmation artifact that references the source audit digest.
- **CODE FACT:** [`src/crucible/cli.py`](../../../src/crucible/cli.py) exposes the
  optional `--confirm` path.
- **CODE FACT:** [`tests/test_confirm_contract.py`](../../../tests/test_confirm_contract.py)
  checks that confirmation leaves the L2 audit unchanged and does not promote its
  finding from `CANDIDATE`.
- **CODE FACT:** the L2.5 section of [`docs/ROADMAP.md`](../../ROADMAP.md) already
  described confirmation as implemented, contradicting the earlier summary in the
  same document.
- **CONFIRMED BY INDUCTION:** the updated regression assertion failed against the
  stale emitted limitation, then passed after correction. Restoring the old wording
  as a negative-control mutation made it fail again.

## Remediation

Updated the live detector docstring, its emitted limitation, and the roadmap summary.
The wording now says that optional L2.5 confirmation records an executor verdict as
a separate observation and does not modify the deterministic L2 audit. Updated the
contract test to protect that boundary instead of requiring the stale word “LLM”.

No finding logic, confirmation verdict, or artifact schema changed. Historical audit
outputs and dated decision/red-team records were left intact as records of what they
said at the time.

## Red-team verification

- Before the fix, `tests/test_semantic_redundancy_contract.py::test_redundancy_has_limitation_documented`
  failed because the emitted text said the layer was deferred.
- Negative control: restored the stale limitation temporarily; the updated test
  failed on the missing `optional L2.5 confirmation` contract, then the correction
  was restored.
- After the fix, the focused semantic-redundancy and confirmation suites passed.
- The complete local suite, `./.venv/bin/python -m pytest -q`, exited **0**.
- `git diff --check` passed.

## Scope limit

This confirms that the confirmation path exists and preserves the original L2 audit
under the tested contract. It does **not** establish that executor opinions are
ground truth, that semantic redundancy is generally well calibrated, or that every
current document has been checked for stale status claims.

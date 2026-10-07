# Check coverage: competing hypotheses and local experiment

**Date:** 2026-10-07  **Branch:** `main`  **Base:** `e29c8d7`
**Scope:** local compiler and auditor behavior; no network or external corpus
fetches.  **Status:** exploratory evidence; no semantic classifier selected.

## Question and broken invariant

The auditor's current `REQUIREMENT_WITHOUT_CHECK` consumer treats a nonempty
skill-level `checks` list as evidence that every normative rule has a
verification path. The invariant under review is narrower:

> A rule is covered only when there is evidence that a check verifies that
> rule; the existence of a check-shaped record elsewhere in the skill is not
> sufficient.

This differs from the earlier symptom, where a workflow item was extracted as
a check. It predicts a sibling false negative even when the extracted item is
a genuine check but unrelated to the rule.

## Evidence provenance

- Prior workflow/check reproduction and rejected same-line mitigation:
  [red-team adjudication](../red-team/2026-10-07-check-heading-adjudication.md),
  recorded in commit `e29c8d7`.
- Four route fixtures and the 427-file single-reviewer pilot:
  [check-heading evaluation](2026-10-07-check-heading-evaluation.md). The pilot
  is a consumed set, not independent ground truth.
- Live implementation reviewed: `_extract_checks`,
  `_extract_procedural_steps`, and `_check_requirement_without_check` at base
  `e29c8d7`.

## Predictions before the run

1. If extraction route or heading words establish semantics, the two workflow
   controls should not appear as checks.
2. If source-span overlap establishes that an item is only workflow, it should
   distinguish the workflow controls without rejecting real checks.
3. If `oracle_kind` establishes verification semantics, it should separate
   verification operations from execution/presentation steps.
4. If skill-level nonempty checks establish rule coverage, a clearly unrelated
   genuine check should not suppress a missing-coverage candidate.

## Experiment and observed results

Ran the existing four source-informed fixtures through both current extraction
functions and `_extract_oracle_kind`. Also compiled and audited a fifth fixture
with a real signature check unrelated to its normative idempotency rule.

| Fixture | Expected human label in the source-informed pilot | Extracted check | Extracted step at same source span | `oracle_kind` |
|---|---|---:|---:|---|
| Response status exactly 200 (`Validation Criteria`) | CHECK | yes | no | `unknown` |
| Search markets (`Live Odds Check`, numbered) | WORKFLOW | yes | yes | `unknown` |
| Verify signature matches publisher key | CHECK | yes | no | `command` |
| Run export, print artifact path | WORKFLOW | yes | no | `command` |

The fifth fixture contained `Requests MUST be idempotent` and a `Checks`
section item, `Verify the detached signature matches the publisher key.` The
compiler extracted the item as a check; the auditor emitted no
`REQUIREMENT_WITHOUT_CHECK` finding. The check is plainly about a signature,
not request idempotency, so it cannot establish coverage of that rule.

A sixth fixture contained two rules, `The request MUST be authenticated` and
`The request MUST be idempotent`, plus one check: `Verify the request signature
against the publisher key.` It is relevant to authentication, but not
idempotency. The auditor again emitted no `REQUIREMENT_WITHOUT_CHECK` finding.
This demonstrates that the current skill-level boolean also erases partial
coverage.

A simple shared-token link proposal cannot distinguish the two rules in that
partial fixture: both rules share `request` with the check, while the check
contains no `idempotent` token. A tokenizer that removes common words still
leaves `request` on both sides. This is a hand-inspected counterexample to
plain lexical overlap, not a benchmark of every lexical linker.

The first harness attempt passed a temporary directory with no `SKILL.md` and
was rejected by `compile_corpus` (`corpus contains no SKILL.md files`). The
fixture was moved under a temporary skill directory and rerun. No repository
source was changed by either run.

Focused route-fixture test:

```text
.venv/bin/python -m pytest -q \
  tests/test_compiler_contract.py::test_check_extraction_routes_have_positive_and_workflow_control_fixtures
1 passed
```

The two added characterization tests for unrelated and partial checks passed
alongside the original workflow characterization and the existing related
check control (**4 passed**). A negative-control mutation changed the auditor
guard from `if not rules or checks` to `if not rules`; all three
characterization tests then failed because the missing-check finding appeared.
The guard was restored and the same four tests passed again. The tests pin
current defective behavior and are named as characterizations; they do not
claim that suppressing those findings is correct.

## Hypothesis adjudication

| Hypothesis | Result | Evidence and limit |
|---|---|---|
| H1: check-family heading means check | **Falsified as a general rule** | The `Live Odds Check` item is a workflow control. Heading is useful extraction context, not ground truth. |
| H2: same-span step/check overlap means workflow | **Insufficient; reject as classifier** | It catches the numbered search workflow, but misses the run-and-print workflow. The prior 427-file impact replay would also add ten candidates, several plausible checks. |
| H3: non-`unknown` `oracle_kind` means meaningful verification | **Falsified** | Both signature verification and run-and-print are `command`; the valid exact-status criterion is `unknown`. This field describes a lexical oracle shape, not rule coverage. |
| H4: observable acceptance predicate can separate the four cases | **Promising, unvalidated** | The two CHECK fixtures contain a determinate comparison; the two WORKFLOW controls do not. This is a post-hoc fit to four deliberately selected fixtures and is not evidence of general accuracy. |
| H5: any check in a skill covers its rules | **Falsified** | The unrelated signature-check fixture suppresses the idempotency requirement candidate. This remains false even if extraction perfectly distinguishes checks from workflow. |
| H6: skill-level boolean is enough when a skill has some relevant coverage | **Falsified** | The partial fixture has one check relevant to authentication and another uncovered idempotency rule; the auditor suppresses the candidate for both. |
| H7: shared-token overlap can map checks to rules | **Falsified for the partial fixture** | Both rules share `request` with the authentication check, so token overlap cannot distinguish which rule is covered without stronger structure or semantic evidence. |

The most consequential result is H5: check/workflow classification alone cannot
repair skill-level coverage accounting. The auditor needs rule-to-check
relationship evidence, or it must report that relationship as unresolved.

## Decision trail

| Decision | Disposition | Why | Reopen condition |
|---|---|---|---|
| Treat check-family titles as semantic labels | Rejected | Workflow counterexample in the consumed pilot. | A separately adjudicated corpus establishes a narrower title contract. |
| Exclude every check that overlaps a procedural step | Rejected | Prior replay added ten candidates with plausible verification operations; current fixture matrix also shows overlap misses another workflow shape. | A new rule with measured precision/recall and explicit abstention behavior. |
| Treat `oracle_kind != unknown` as coverage | Rejected | It confuses run-and-print with signature verification and misses exact status criteria. | A changed, tested meaning for `oracle_kind` that includes rule linkage; current field does not. |
| Patch a semantic heuristic now | Deferred | Four curated controls are too small and post-hoc; no fresh independently labeled corpus is present locally. | Independent labels plus explicit consumer/compatibility impact replay. |
| Treat rule-check linkage as the missing design dimension | Working hypothesis | Unrelated-check experiment falsifies skill-level existence as a coverage proxy. | A counterexample where linkage evidence still yields an incorrect coverage verdict, or an impact study showing the candidate model is unusable. |
| Keep one coverage boolean per skill | Rejected | The partial fixture proves it cannot represent one covered rule alongside another uncovered rule. | Reopen only if the product explicitly limits its claim to skill-level presence and renames/narrows the finding accordingly. |

## Candidate integral design, not yet adopted

Keep extraction structural and deterministic. Separate coverage into three
states at the audit boundary:

1. **No check candidate extracted** — retain the existing missing-check
   candidate, with its current coarse scope stated.
2. **Check candidate exists; rule linkage unknown** — emit an explicitly
   unresolved coverage candidate rather than silently suppressing the gap.
3. **Rule-check link evidenced** — only this state can support a coverage
   claim.

Possible link evidence needs its own comparison: explicit source annotations,
deterministic rule references, and confirmation-layer proposals all have
different author burden, recall, determinism, and trust costs. Plain token
overlap is insufficient on the partial fixture. A confirmation result must
remain a separate artifact; it must not silently rewrite the L1 IR or the
deterministic L2 audit. The current L2.5 prompt for
`REQUIREMENT_WITHOUT_CHECK` assumes there are zero extracted checks, so it
cannot simply be reused for an unresolved rule-check relation.

This design could add a finding class or alter the meaning of an existing one.
Before implementation, inventory all readers (`auditor`, `confirm`, `graph`,
`consolidation`, reports, CLI) and replay finding-count and artifact-digest
changes. If persisted IR fields are added, apply schema-evolution rules rather
than assuming the `skill-ir/v1` digest is unaffected.

## Next discriminating experiment

Before selecting the link mechanism, add adversarial pairs where:

- one normative rule has a relevant check and an unrelated check;
- one skill has several rules but a check that covers only one;
- rules and checks share a generic noun but differ on the required property;
- a check states a direct condition without a verification verb;
- a workflow invokes `run`, `check`, or `verify` but only gathers or presents
  data;
- an operation has an implicit but judgeable outcome, such as signature
  verification;
- the same text appears under a check-family heading and under an ordinary
  workflow heading.

For each pair, state expected rule-check links before running the compiler and
auditor. Compare candidate mechanisms on the same fixtures. Do not use the
four current controls as a tuning-and-validation set simultaneously; reserve
fresh cases for falsification. The local installed/pinned source corpora used
by earlier audits are not present in this checkout, so broad corpus impact
cannot be measured without reacquiring them. That acquisition is not needed
for the next fixture-level experiment.

## Limits

This experiment confirms current behavior on six local fixtures. Human labels
for the four route controls come from a single-reviewer, consumed pilot; the
unrelated and partial fixtures have intended links authored for this
experiment, not independent adjudication. It does not estimate corpus
accuracy, establish a semantic classifier, or prove that explicit annotations
are the best link source. Two characterization tests were added; no production
code or persisted schema changed.

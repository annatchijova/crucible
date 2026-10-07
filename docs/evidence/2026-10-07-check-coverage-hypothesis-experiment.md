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

We also ran the existing deterministic Jaccard token primitive on those exact
three strings. After the current stopword filter, each rule tokenizes to two
tokens (`request` plus its property); the check tokenizes to six tokens. Both
rule-to-check scores are exactly `1/7`. In this partial-coverage fixture, a
threshold at or below `1/7` proposes both edges (one correct of two); a higher
threshold proposes neither. No threshold on this feature separates the
covered rule from the uncovered one. This is an evaluation of one transparent
baseline on one adversarial case, not a general accuracy claim.

On this same partial fixture, the trivial edge baselines are explicit: “no
edges” has zero recall (precision is undefined with no predictions); “connect
every check to every rule” has 1/2 precision and full recall; the Jaccard
baseline ties both possible edges and can only produce one of those two
outcomes at a scalar threshold. An author annotation can declare the intended
single edge, but remains a declaration and still requires adequacy review. The
model alternative has no measured result in this offline run.

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

Keep extraction structural and deterministic. Separate relation provenance at
the audit boundary:

1. **No check candidate extracted** — retain a structural missing-check
   candidate, with that limited scope stated.
2. **Link unknown** — a check candidate exists but no relation has been
   established; emit unresolved coverage rather than silently suppressing it.
3. **Link declared or proposed** — retain provenance (`author`, `deterministic`,
   or `model`) and do not call this verified coverage.
4. **Link adjudicated** — record who/what reviewed the relation, evidence and
   limits. Even this is text-level or behavior-level evidence within its stated
   scope, not universal proof that the check is sufficient.

Possible link evidence needs its own comparison: explicit source annotations,
deterministic rule references, and confirmation-layer proposals all have
different author burden, recall, determinism, and trust costs. Plain token
overlap is insufficient on the partial fixture. A confirmation result must
remain a separate artifact; it must not silently rewrite the L1 IR or the
deterministic L2 audit. The current L2.5 prompt for
`REQUIREMENT_WITHOUT_CHECK` assumes there are zero extracted checks, so it
cannot simply be reused for an unresolved rule-check relation.

## Link-source comparison and consumer impact

This comparison is architectural, not an accuracy benchmark. No fresh labeled
corpus or network model run was available; no external API was called.

| Link source | What it establishes | Failure mode / cost | Current consumer fit |
|---|---|---|---|
| Author-declared stable IDs in source | The author explicitly claims a rule-check relation. | Declaration can be wrong or stale; imported skills remain unannotated; generated `rule-0001` IDs are not a stable author contract. | Parsing into L1 would change `skill-ir/v1`; alternatively keep declarations in a separate versioned source map. |
| Deterministic lexical candidate | A repeatable string-level association worth review. | Generic shared terms over-link; paraphrases miss; the partial fixture has equal shared-term evidence for covered and uncovered rules. It cannot prove semantic coverage. | Could be produced in L2 as candidates, but counts/precision/recall are unmeasured. Avoid persisting candidate relations in L1 until utility is shown. |
| L2.5 model proposal | A model's contextual observation about which check may address a rule. | Non-deterministic, may miss/overstate links, and must not directly change L2's verdict. No Nebius call was made. | Current prompt builder for `REQUIREMENT_WITHOUT_CHECK` asserts zero extracted checks and asks only whether the skill has missed checks; it does not ask for per-rule links or return check IDs. `MockConfirmExecutor` uses non-empty-line count for single-skill prompts, not semantics. A new typed prompt/output contract is required. |
| Human adjudication | A reviewer accepts/rejects a proposed rule-check relation with source context. | Reviewer time and fatigue; requires a usable diff and provenance. | The intended links in these fixtures were assigned by this reviewer, not independently adjudicated. Any production review should be separately recorded and must not mutate source or audit artifacts silently. |

The prompt was built offline with a hypothetical unresolved-link finding. The
observed user prompt contained both normative rules and the check, but still
asked whether the skill had “zero extracted checks”; it did not ask for a
rule-to-check relation or check IDs. This falsifies reuse of the existing
`REQUIREMENT_WITHOUT_CHECK` confirmation prompt for partial coverage. The
confirmation artifact can carry observations separately, but any proposed
check ID must be validated against the source IR's actual check IDs before it
is accepted as a relation record. Skill text remains untrusted data; prompt
envelopes alone are not an authorization control.

### Local consumer-count probe

Compiled `tests/fixtures` (11 skills) and counted skills with at least one
normative rule and at least one extracted check: two (`fastapi`: 5 rules/2
checks; `developing-with-streamlit`: 1 rule/4 checks). The existing audit
produced four `REQUIREMENT_WITHOUT_CHECK` findings in that fixture corpus.
These are curated test fixtures, not a representative corpus. The result only
shows that adding one unresolved-link finding per rule could add up to six
records in this tiny set; it is not a useful production-volume estimate.

### Compatibility surface inspected

- **L1 IR:** adding rule/check links to each skill changes persisted IR content
  and its digest. `graph.py` currently requires exactly `skill-ir/v1`; it would
  need an explicit reader/migration plan if L1 changes.
- **L2 audit:** an added per-rule finding can fit the current finding shape,
  but changes the class taxonomy and audit digest. If structured `check_ids` or
  relations are added, audit version and readers need review.
- **L2.5 confirmation:** new finding class needs a prompt builder and trust-safe
  parser. Structured proposed links require a confirmation schema version
  decision and ID validation. The current mock cannot evaluate semantic links.
- **L8/report and human output:** the HTML/API/report paths render arbitrary
  finding classes generically, but the composite report summarizes counts and
  seals downstream digests; new evidence changes those digests even if shape
  stays the same.
- **Bob repair:** `RuleBasedProposer` handles the existing
  `REQUIREMENT_WITHOUT_CHECK` class by inserting generic checks. A new
  unresolved-link class has no deterministic repair pattern, which is safer
  than pretending a generic added check resolves a particular rule. LLM repair
  behavior still needs a separate gate and relationship-aware re-audit.
- **Mutation lab:** the check-removal mutation expects the existing
  `REQUIREMENT_WITHOUT_CHECK` class. Preserve this invariant if the class is
  narrowed to “no check candidate extracted”; add a separate mutation for a
  deleted or wrong rule-check link if relation records are implemented.
- **Consolidation:** current merge coverage preserves rules and checks as text
  items, not their cross-relations. Any persisted link map must be merged with
  source provenance or explicitly rejected when it cannot be preserved.

This favors an additive, versioned relation artifact over changing the L1 IR
immediately, but does not settle where the eventual relation belongs. A
candidate shape is `crucible-coverage-map/v1` referencing both source digests
and carrying rule ID, check ID, relation state, evidence provenance and
adjudication. This artifact could preserve the deterministic L2 audit while a
new L2 consumer reports unresolved or adjudicated coverage; whether that
creates an unacceptable second audit authority remains open. The main unresolved
choice is which relation source can support each named status.

This design could add a finding class or alter the meaning of an existing one.
The first consumer inventory is recorded above; before implementation, validate
it against the exact proposed artifact shape and replay finding-count and
artifact-digest changes. If persisted IR fields are added, apply
schema-evolution rules rather than assuming the `skill-ir/v1` digest is
unaffected.

## Next discriminating experiment

### Synthetic link-source matrix: pre-registered predictions and result

Before running `docs/evidence/check_link_source_matrix.py`, predictions were
recorded in the session: the explicit map would reproduce annotations exactly
(including an intentionally false annotation); Jaccard at `1/7` would recover
the clear and exact-condition links but over-link both rules in the partial
case; `1/5` would remove that extra edge while missing the correct partial
edge. The ambiguous policy case would be disclosed separately, not used to
choose a threshold. No model metric would be reported without an actual model
run and independent labels.

The offline harness compiled six synthetic fixtures through the current L1
compiler. It emitted IR digest
`sha256:8823f1d517839d85e38c534c7762b29c35eb3eba2d865639db1c9490118c38bd`.
Two consecutive runs produced byte-identical JSON (`cmp` passed). Against the
five labeled cases (three expected edges), the observed counts were:

| Mechanism | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| No links | 0 | 0 | 3 | undefined | 0/3 |
| All pairs | 3 | 3 | 0 | 3/6 | 3/3 |
| Author declarations | 2 | 1 | 1 | 2/3 | 2/3 |
| Jaccard ≥ 1/7 | 3 | 1 | 0 | 3/4 | 3/3 |
| Jaccard ≥ 1/5 | 2 | 0 | 1 | 2/2 | 2/3 |

The explicit-declaration false positive is the intentionally incorrect
annotation on the unrelated-signature fixture. Its false negative is the
unannotated direct status condition. In the partial fixture both rule/check
pairs score `1/7`; the low threshold emits both, while the high threshold
emits neither. The unresolved policy case scores `1/4` and would still be
proposed by both thresholds; it was excluded from the metrics, so neither
threshold demonstrates abstention. A threshold does not supply confidence or
semantic adequacy.

The thresholds are comparison points, not calibrated choices: `1/7` was
observed in the previously consumed partial fixture and this set is not
independent. These exact finite counts describe only this author-labeled
synthetic matrix. They are not corpus estimates, have no useful confidence
interval, and do not rank general-purpose mechanisms. The sidecar declarations
are harness labels only; the current Markdown parser does not support them.
No model/API was called, and no L1, L2, or persisted schema changed. Reproduce
with `.venv/bin/python docs/evidence/check_link_source_matrix.py`.

This result confirms the predicted trade-off but does not select a source of
truth. Preserve declarations, deterministic proposals, human adjudication, and
model observations as distinct provenance. The next step is a fresh
independently labeled set with explicit abstention criteria, then evaluate
whether any relation artifact can be consumed without becoming a second audit
authority.

## Next discriminating experiment (expanded plan)

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

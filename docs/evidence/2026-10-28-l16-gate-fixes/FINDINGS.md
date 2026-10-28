# L16 gate: three verdicts that depended on an unrelated skill's name, fixed

**Date:** 2026-10-28
**Follows:** [live L16 run on vantaflow](../2026-10-24-l16-live-real-corpus/FINDINGS.md),
which recorded G-01 and G-02 and left them unpatched.
**Code:** `src/crucible/consolidation.py` (`_evaluate_novelty`,
`_involves_skill`, `_report`). **Tests:** the last four in
`tests/test_consolidation_contract.py`; each fails on the code before this
change and passes after it, except the negative control, which passes on both.

## The common defect

Two of the auditor's corpus-level findings are attributed to one skill of a
group by name order: `STRUCTURAL_REDUNDANCY` to the first skill holding the
duplicated text, `SEMANTIC_REDUNDANCY` to the lexicographically smaller name of
the pair. The gate read those findings by their attributed skill. So whether a
merge was accepted could depend on what an unrelated skill was called.

## G-01: a moved duplication read as a new one (fixed)

`STRUCTURAL_REDUNDANCY` is now compared by its own identity, the duplicated
rule text, looked up in the IR by the `(skill, rule_id)` the finding cites. A
duplication is new only if that text was not already duplicated before the
merge.

Synthetic reproduction: the built-in retry cluster plus one outside skill that
shares the rule `Retries MUST have a finite budget.`, merged as
`standard-retry`.

| Outside skill | Before | After |
|---|---|---|
| `shared-policy` (sorts between members and merged name, so the attribution moves) | REJECTED, `NEW_FINDINGS: STRUCTURAL_REDUNDANCY` | ACCEPTED |
| `zeta-policy` (sorts after, the attribution stays) | ACCEPTED | ACCEPTED |

Negative control: a merge that copies a rule verbatim from the outside skill,
so the merge itself creates a duplication, is still REJECTED with
`STRUCTURAL_REDUNDANCY` in `new_findings`.

**On the real skills.** [`replay_vantaflow_slice.py`](replay_vantaflow_slice.py)
reruns the four-skill slice from `vantaflow` @ `f88a34d0f75e`. The Nemotron
proposal text from 2026-10-24 was not saved, so the script replaces it with a
deterministic union of both members under the name the model chose. With no
model in the path:

| Cluster | Before | After |
|---|---|---|
| `bug-debugger` + `dev-bug-debugger` | REJECTED, `NEW_FINDINGS: STRUCTURAL_REDUNDANCY` | ACCEPTED |
| `debugger` + `prompt-debugger` | ACCEPTED | ACCEPTED |

The "before" row reproduces the refusal recorded on 2026-10-24 with the same
reason. That confirms the refusal came from the gate and not from the content
of the model's merge. It does not show that the lost Nemotron merge would now
be accepted, since that text no longer exists.

## G-02: `redundancy_resolved` was a copy of the outcome (fixed, and re-diagnosed)

The 2026-10-24 record said that `redundancy_resolved` was corpus-wide and
turned `false` because of the other, untouched cluster. Reading the code shows
a simpler cause: the field was `outcome == ACCEPTED`. Any merge rejected for
any reason reported its redundancy as unresolved. The other cluster played no
part in it.

It is now measured. `True` or `False` says whether the proposal, once applied,
leaves the merged skill outside every `SEMANTIC_REDUNDANCY` pair. `None` means
the gate stopped before re-auditing, so the value was never evaluated. A
rejected merge can therefore report `True`: it is a property of the proposal
under test, not a statement that the corpus changed. Rejected merges are never
applied.

## G-03: persisting redundancy missed by name order (found and fixed here)

While fixing G-01 I found the same pattern in the redundancy-gone check, which
only looked at findings attributed to the merged skill. Take a merge that is
still lexically redundant with an outside skill. If the outside skill was named
`zzz-retry`, the finding was attributed to the merged skill and the gate
refused with `REDUNDANCY_PERSISTS`. If it was named `aaa-retry`, the finding
was attributed to `aaa-retry` and the merge was **accepted**. That is the
dangerous direction: a false acceptance, not a false refusal.

The check now recovers the pair from the evidence with the same parser L2.5
confirmation uses (`confirm._parse_semantic_redundancy_pair`) and refuses in
both cases.

## Known variant not fixed

`NORMATIVE_CONFLICT` and `CONDITIONAL_CONTRADICTION` are also pairwise and
attributed by order, so in principle they can re-anchor the same way. The
evidence of those findings is a free-form sentence, and they fire rarely
because subject extraction yields a subject in 27 of 2806 real skills
([ADR-0027](../../decisions/0027-defer-imperative-subject-extraction.md)).
Comparing them by identity would mean parsing prose or adding a structured
participant field to the audit schema. Neither is done here. A false refusal
from this variant remains possible and would show up as `NEW_FINDINGS` naming
one of those classes on a skill outside the cluster.

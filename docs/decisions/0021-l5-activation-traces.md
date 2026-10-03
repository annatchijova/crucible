# ADR-0021: L5 Property Observation Activation Traces

**Status:** Accepted
**Date:** 2026-10-03
**Reversibility:** high; `evidence` stays the same type (`str`) in the
same three-field observation shape, only its content changed

## Context

`docs/STATUS_AND_TODO.md`'s P2 item #10 ("Runtime activation traces")
noted that the L5 behavioral differential's report says which variant
ran but not how the model's output related to each property: every
observation's `evidence` field was a static sentence —
`f"output checked for: {prop['description']}"` — identical regardless of
whether the property PASSED, FAILED, or why. There was no way to see,
from the sealed report alone, which specific text in the model's real
output justified a verdict.

## Decision

Each `_check_*` function in `behavioral.py` (`_check_mentions_budget`,
`_check_respects_exception`, `_check_no_unbounded_retry`,
`_check_mentions_idempotency`) now returns `(status, trace)` instead of
a bare status string, where `trace` is `{basis, matched_keyword,
snippet, keywords_checked}` — which keyword/pattern actually matched (or
`None`), a readable snippet of the real output around that match
(original case, not the lowercased/normalized text used for matching),
and the full list of keywords that were searched. `_format_evidence`
renders this trace into a one-line string.

### Why `evidence` stays a string, not the structured dict directly

The first implementation returned the trace dict as `evidence` itself.
Running the full test suite caught this immediately: `replay.py`'s
`validate_bundle` (the sealed `crucible-capture-bundle/v1` contract for
R2/R3 offline replay) requires every observation to have **exactly**
the fields `{property_id, status, evidence}` (`_fields`, a closed-set
check) and requires `evidence` to be `str` (`_text`). That is a
deliberately strict, sealed contract for tamper-evident replay — not an
incidental shape to relax so a new field fits. Relaxing it to accommodate
a new feature would weaken exactly the kind of validation this project
otherwise treats as load-bearing (see §4.2/§5.2 of the engineering
discipline this repo follows: patch the live contract, don't widen it to
dodge a failing check). The richer trace is therefore folded into one
descriptive string (`_format_evidence`) instead of added as a new field
or a changed type — zero schema change to the sealed bundle contract.

### What counts as a trace, and what it does not claim

The module docstring now states explicitly: this is a deterministic,
lexical trace of which keyword appeared in the model's real output, not
a claim about the model's internal reasoning, attention, or that it
"used" the skill text in any mechanistic sense. A model could produce a
matching keyword by coincidence, or express an equivalent idea without
using any searched keyword — an absence this oracle cannot distinguish
from a genuine gap. Bounded, honest observability, not a causal
activation proof — consistent with how every other oracle in this
project states its own limitations rather than overclaiming.

### Viewer enhancement

`viewer.py`'s behavioral-differential table now wraps each
`property_id=status` pair in a `<span title="...">` carrying the
evidence string as an HTML tooltip — pure HTML, no `<script>`, preserving
the viewer's own stated constraint (read-only, `html`/`json`/`typing`
imports only).

## Alternatives rejected

- **Relax `replay.py`'s validator to accept a dict `evidence`.** Rejected:
  widening a sealed, tamper-evident contract to fit a new feature is
  exactly the shortcut this project's own discipline warns against.
- **Add a new field (e.g. `activation_trace`) alongside `evidence`.**
  Rejected for the same reason: `_fields` requires an exact, closed key
  set; any new key breaks the same validator just as much as changing
  `evidence`'s type does.
- **A new, separate L5 artifact for traces, outside the sealed bundle.**
  Not pursued: the existing `evidence` field already exists for exactly
  this purpose (per-observation justification) and was simply
  underused (a static sentence); fixing what it contains is simpler and
  more honest than adding a parallel structure.

## Consequences

Accepted now:
- `evidence` genuinely reflects the real output: which keyword matched
  and where, or which keywords were searched and found absent.
- No change to the sealed `crucible-capture-bundle/v1` contract, the L5
  report schema's key set, or any existing consumer (`report.py`,
  `viewer.py` for findings/mutation evidence, which read `evidence`
  generically as text and were already compatible).
- 4 new falsifiable tests in `tests/test_behavioral_contract.py`: PASS
  evidence names the real match, FAIL evidence lists what was searched,
  evidence stays plain non-empty text (the capture-bundle invariant,
  tested explicitly so a future change that reintroduces a dict/struct
  value fails loudly here instead of three layers downstream in
  `replay.py`), and two different real outputs passing the same property
  via different keywords produce different evidence text (proving the
  trace is real, not a disguised static string). Full suite green, no
  regressions.

Deferred:
- A trace that distinguishes "model said something semantically
  equivalent without the exact keyword" from "the property genuinely
  does not hold" — this lexical oracle cannot make that distinction by
  construction, independent of this change.
- Extending the same trace pattern to any future property check added
  to `PROPERTY_CHECKS`; the pattern (`_snippet`, trace dict,
  `_format_evidence`) is established here for reuse, not retrofitted
  everywhere a check exists.

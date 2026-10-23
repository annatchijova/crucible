# L3 composition is silent on an independently authored corpus

**Date:** 2026-10-23  **Branch:** `main`  **Base:** `094a087`
**Scope:** local compiler and graph behavior on two real corpora. No network
calls beyond cloning the pinned external corpus; no model involved.
**Status:** reproduced defect set; no fix applied in this record.

## Question

An external review argued that a 818-skill corpus implies 334,153 potential
skill pairs and that per-file scanning therefore cannot answer composition.
The arithmetic is correct. The question this record answers is narrower and
empirical: what does Crucible's composition layer actually produce on that
corpus?

## Firstness — what was observed

Two corpora, same command (`python -m crucible.cli <root>`), same base commit:

| Corpus | Skills | Graph edges | Audit findings | Wall | Peak RSS |
|---|---|---|---|---|---|
| `~/.claude/skills` (author) | 101 | 86 | 108 | 0.54 s | 33 MB |
| `mukul975/Anthropic-Cybersecurity-Skills` @ `54a7988` | 818 | **0** | 1056 | 3.96 s | 80 MB |

Further measurements on the same two corpora:

- `composes_with` section declarations: **0 of 818** and **0 of 101**.
- `delegates_to` section declarations: **0 of 818** and **0 of 101**.
- All 86 author-corpus edges carry `extraction_method: "description"`.
- The `limitations` array is **byte-identical** between the run with 86 edges
  and the run with 0 edges.
- `graph_properties` on the external corpus contains 818 entries, one
  `DISCONNECTED_COMPONENT` observation per skill.

## Secondness — how this deviates from the expected baseline

`docs/COMPETITIVE_BOUNDARY.md` lists typed composition as a candidate core
boundary and separates redundancy, composition, reinforcement and
contradiction. The expected baseline for a corpus of 818 real, related
security skills is therefore *some* composition signal, or an explicit
statement that none could be computed.

What the report emits instead is `"total_edges": 0` with the same three
limitation entries it emits for a corpus where composition did resolve. A
reader cannot distinguish these two states from the artifact:

1. composition was analyzed and this corpus has no composition problems;
2. this corpus uses no convention the extractor reads, so nothing was
   analyzed at all.

State 2 is what happened. The artifact reports it in the shape of state 1.
This violates the honest-degradation rule in `CLAUDE.md` §5.3: a guarantee
that the environment did not confirm must not be emitted as a silent pass.
There is no `ABSTAIN` or `NOT_APPLICABLE` outcome on this path.

## Thirdness — the general rule, grounded in the code

`graph.py:_build_edges` has exactly two edge sources:

1. bullets under a section heading containing `composes with` or
   `delegates to` (`compiler.py:486-487`, via `_extract_relations`);
2. trigger patterns matched against the frontmatter `description`, resolving
   targets that name another skill (`graph.py:144-151`, `_extract_targets`).

Both require an author to name the other skill explicitly. No edge is ever
derived from methodological content. The rule:

> Crucible's composition layer detects **declared cross-references**, not
> methodological interaction. Its output is a function of authoring
> convention, so on a corpus that does not use that convention it is
> structurally silent, and silence is currently indistinguishable from a
> clean result.

The author corpus produces 86 edges because its descriptions say "Sibling
of", "Pairs with" and "Composes with" in prose. That is a property of who
wrote it, not of the methodologies.

## Refutation attempted

The benign hypothesis was that the wrong convention was measured.
`TECHNICAL.md:107` documents `## Composes with`/`## Delegates to` as the real
convention — L16 consolidation auto-rewrites exactly those bullets. So the
measured convention is the intended one. The hypothesis is refuted, and it
yields a second observation: L16's section-bullet rewrite path has no
exercise on either real corpus either.

A second benign hypothesis was that 818 unrelated skills genuinely have no
composition. This is not refuted by this record and cannot be, because the
extractor never examined methodology. That is precisely the gap: the corpus
may or may not contain real composition defects, and the current artifact
carries no evidence either way.

## Defects recorded

| ID | Defect | Evidence | Severity claim |
|---|---|---|---|
| C-01 | Zero resolvable relations is reported as `total_edges: 0` with no abstention; silence is indistinguishable from a clean composition result | identical `limitations` across the 86-edge and 0-edge runs | Honest-degradation violation; reader can overread a clean result |
| C-02 | The `composes_with`/`delegates_to` section path has 0 hits across 919 real skills; the only live path is description-text mention | per-corpus counts above | Unexercised path, including L16's rewrite gate |
| C-03 | Typed composition measures declared cross-reference, so the `COMPETITIVE_BOUNDARY` claim does not hold on independently authored corpora | `graph.py:_build_edges` has no methodology-derived edge source | Scope of a published differentiator claim |

## Limits of this record

- Two corpora, one of them the author's own. This is not a sample of the
  skill ecosystem and gives no base rate for how often the convention is used.
- The external corpus is already consumed: it was used on 2026-10-02 to fix
  three compiler defects, so it cannot support a generalization claim. It is
  sealed as `TUNING_CONSUMED` in [`corpus-provenance.json`](corpus-provenance.json)
  (818 skills, manifest `sha256:6a5b3836…`, seal `sha256:b8686089…`). The
  manifest reproduces `MATCH` on recompilation; the recorded commit is a claim
  the seal binds but does not verify.
- Timings are single runs on one unloaded machine. They indicate order of
  magnitude, not a cost model.
- No fix is proposed here. C-01 is a reporting contract decision, C-03 is a
  claim-scope decision, and neither should be patched before the contract is
  chosen.

## Consequence for the external review's framing

The pair-space argument does not describe this system's cost: Crucible never
traverses the pair space, and the 818-skill run cost 3.96 s because edge
construction is proportional to declared references, of which there were
none. The defensible version of the same concern is C-03: undeclared
methodological interaction is outside the current extractor, and the
artifact does not say so.

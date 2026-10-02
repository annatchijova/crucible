# First real external-corpus run — mukul975/Anthropic-Cybersecurity-Skills

**Date:** 2026-10-02
**Corpus:** [mukul975/Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills), 818 skills, cloned read-only, not committed to this repo. This is the corpus chosen for Crucible's own demo and fills `docs/STATUS_AND_TODO.md`'s open "corpus OSS independiente" gap.

This is the first time Crucible's compiler and auditor have been run against
a large, real, independently-written corpus rather than the author's own
~90-skill corpus or small fixtures. It immediately found real defects —
not in the audited skills, but in Crucible's own compiler.

## Compiler: three real parsing gaps, closed by moving to a real YAML parser

Running the (then hand-rolled) frontmatter parser against all 818 skills
crashed the whole batch on the first unsupported construct. Fixing each
discovered shape one at a time surfaced a new, deeper one immediately
after:

| Shape | Example | Compile success after fix |
|---|---|---|
| YAML sequence (`tags:` / `- item`) | `tags:\n- red-team\n- dpapi` | 490 -> 721 / 818 |
| Plain multi-line scalar (no `>`/`|`) | `description: ...\n  more text` | (included above) |
| Quoted multi-line scalar + `''` escape | `description: 'text\n  more\n  '` | 721 -> 724 / 818 |
| Sequence nested one level inside a mapping | `metadata:\n  tactics:\n  - item` | 724 / 818 (94 left) |
| Sequence **of mappings** (full recursion) | `techniques:\n- id: T1583\n  name: ...` | required a real parser |

Each hand-rolled special case fixed one shape and revealed the next one
underneath it — the actual signal that the fix needed was a real YAML
parser (`yaml.safe_load`, PyYAML now a required dependency), not another
special case. `src/crucible/compiler.py` now delegates frontmatter parsing
to PyYAML entirely (~150 lines of hand-rolled state machine replaced by a
few lines).

**That migration broke 39 of Anna's own 90-skill corpus** — real,
hand-written `description:` fields are usually unquoted prose, and prose
containing a colon followed by a space (`"...a live system: 'acquire the
disk'..."`) is genuinely invalid strict YAML (ambiguous with a new mapping
key), even though it was never a problem for the old lenient parser. This
would have been a much worse regression than the external-corpus gaps that
motivated the migration. Fixed with a narrow, targeted repair
(`_load_yaml_with_colon_repair`): on a YAML scanner error, if PyYAML's own
reported line is a complete top-level `key: text` pair whose value isn't
already quoted/structured, that one line is re-quoted and the parse is
retried; any other kind of error (e.g. inside a nested sequence) still
fails honestly as real invalid YAML.

**Result: 818/818 (mukul975) and 90/90 (author corpus) both compile
cleanly.** 679/679 tests pass (24 new/updated regression tests for the
compiler alone). See `src/crucible/compiler.py` and
`tests/test_compiler_contract.py`.

## Audit: 552 findings across 818 real skills

```
CHECK_WITHOUT_ORACLE            91
CLAIM_WITHOUT_PROVENANCE         3
DESCRIPTION_BODY_GAP           179
IRREVERSIBLE_WITHOUT_REVIEW     49
METHODOLOGICAL_VACUITY           3
MISSING_FAILURE_MODE            57
NON_DETERMINISTIC_INSTRUCTION   20
OVERCLAIM                        1
REQUIREMENT_WITHOUT_CHECK       67
SCOPE_TRIGGER_MISMATCH          54
SECRET_IN_OUTPUT                 1
SEMANTIC_REDUNDANCY              1
UNBOUNDED_RESOURCE               1
UNBOUNDED_RETRY                  4
UNPINNED_DEPENDENCY             19
UNVALIDATED_EXTERNAL_INPUT       2
```

All `CANDIDATE` (none of this corpus's skills compose with each other or
self-reference, so no natively-`CONFIRMED` findings exist). Full audit
artifact: `audit.json` in this directory. Compile+audit over all 818 skills
takes ~3.3s.

## Finding 1 (CONFIRMED BY INDUCTION): SEMANTIC_REDUNDANCY is well-calibrated, not under-triggering

Only one redundant pair was flagged
(`hardening-linux-endpoint-with-cis-benchmark` <->
`hardening-windows-endpoint-with-cis-benchmark`, 29/42 = 0.69 Jaccard
overlap, above the 2/3 threshold). Before trusting that as correct rather
than a missed-detection bug, the same token-overlap computation was run
by hand against three other skill pairs that *sound* similar by name
(all "ransomware analysis" skills):

| Pair | Jaccard overlap |
|---|---|
| `analyzing-ransomware-network-indicators` <-> `analyzing-ransomware-encryption-mechanisms` | 3/40 = 0.07 |
| `analyzing-ransomware-network-indicators` <-> `analyzing-ransomware-payment-wallets` | 3/49 = 0.06 |
| `analyzing-ransomware-leak-site-intelligence` <-> `analyzing-ransomware-payment-wallets` | 7/125 = 0.06 |
| `hardening-linux-...` <-> `hardening-windows-...` (the flagged pair) | 29/42 = 0.69 |

The "ransomware" skills share a domain word but cover genuinely distinct
technical content (network indicators vs. encryption vs. payment wallets
vs. leak sites) and correctly score low. The one flagged pair is a real
near-duplicate: the same CIS-hardening template with only the OS name
changed. **The detector is doing its job correctly on this corpus; the low
count is not evidence of a false-negative gap.**

## Finding 2 (CONFIRMED BY INDUCTION): DESCRIPTION_BODY_GAP has a real false-positive pattern — procedural/workflow-style skills

`DESCRIPTION_BODY_GAP` is the single largest category (179/552, 32%). Its
own docstring already states the honest limitation: the L1 rule extractor
is lexical, looking only for RFC-2119 modals (MUST/SHOULD/MAY) and a
narrow set of imperative/absoluteness patterns, so a skill using normative
language in another form may show "0 rules" even though it has real
structure.

Spot-checking `analyzing-cobalt-strike-beacon-configuration` (flagged:
"description has 17 meaningful tokens but body has 0 rules, 0 checks, 0
procedural steps") confirms this is exactly that false-positive class, not
a genuinely empty skill: the body has Prerequisites, four numbered
`### Step N:` sections each with a real, runnable Python code block, a
`## Validation Criteria` section with seven concrete acceptance checks, and
a references list. None of it is phrased with MUST/SHOULD/MAY — it is
written in plain descriptive/imperative English ("Extract Configuration
with...", "Manual XOR Decryption of..."), a perfectly legitimate and
common style for a procedural skill that this extractor's RFC-2119-centric
pattern set does not recognize as normative structure at all.

**This is the concrete gap behind Anna's original framing** ("categories
that look fine but could be grouped/rewritten/improved"): the check is not
wrong to flag a real absence of RFC-2119 structure, but a large fraction of
its 179 hits on this corpus are likely this same procedural-style pattern,
not skills that are actually empty or low-quality. Not yet quantified how
many of the 179 are this pattern vs. genuinely thin skills — that is the
natural next step before deciding whether/how to extend L1's extractor to
recognize numbered-step-plus-code-block structure as a form of procedural
content, distinct from (and not a replacement for) RFC-2119 rule
extraction.

## Not yet done

- Quantifying the real false-positive rate of `DESCRIPTION_BODY_GAP`
  across all 179 hits (only one was read in full).
- Spot-checking the other finding classes (`CHECK_WITHOUT_ORACLE`,
  `REQUIREMENT_WITHOUT_CHECK`, `MISSING_FAILURE_MODE`, `SCOPE_TRIGGER_MISMATCH`
  — the next-largest categories) for the same kind of style-driven false
  positive.
- Running L2.5/L12 confirmation and L15 recommendation/narration against
  this corpus (would cost real Nebius calls across potentially hundreds of
  candidates; not run here).
- A licensing decision for using this corpus as the public demo (noted
  as open in `docs/STATUS_AND_TODO.md`).

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

## Finding 0 (CONFIRMED BY INDUCTION): a shell comment inside a code fence was silently corrupting section extraction corpus-wide

Spot-checking `CHECK_WITHOUT_ORACLE` findings surfaced something much
larger than a calibration question: 40+ "checks"
on `analyzing-bootkit-and-rootkit-samples` turned out to be bash comments
like `# Check for known UEFI malware patterns` inside a ` ```bash ` fence,
misread as a real Markdown heading.

**Root cause**: `_HEADING` in `compiler.py` matches any `^#{1,6}\s+text$`
line, and `_section_ranges` (which `_extract_checks`,
`_extract_procedural_steps`, and `_extract_relations` all consume) never
excluded lines inside fenced code blocks from heading detection — even
though the sibling function `_code_block_lines` already existed and was
used *elsewhere* in the same file for exactly this purpose. A shell
comment and a level-1 Markdown heading are syntactically identical
(`# text`); fenced code is supposed to be opaque to the surrounding
document's structure, and here it wasn't.

**Measured blast radius before the fix**: 544/818 skills (66%) contained
at least one such comment; **10,749 phantom headings against 11,332 real
ones corpus-wide — nearly 1:1**. A phantom heading whose text happened to
contain "check" or "verification" (extremely common in security-skill
code comments) then matched `_extract_checks`'s substring-based
Checks/Verification section filter, misclassifying an unrelated bullet
list or reference block as a batch of unverifiable "checks."

**Fix**: `_section_ranges` now excludes code-fence lines before matching
`_HEADING` against anything, fixing every downstream consumer at the
source. The same exclusion was also completed in three call sites that
had a partial version of this bug independently (`_extract_checks` and
`_extract_procedural_steps` already excluded code lines on their
*secondary* "anywhere in body" extraction path, but not on their primary
"inside a correctly-titled section" path; `_extract_relations` had no
exclusion at all). Verified by induction, not just by re-running the
suite: re-compiling `analyzing-bootkit-and-rootkit-samples` went from 40+
fabricated checks to 2 real ones (`Verify the integrity of the entire boot
chain`, `Verify Secure Boot configuration...`), both correctly classified
`oracle_kind: command`. Four new regression tests cover the shell-comment-
as-heading case directly, a legitimate Checks section that itself embeds
a code block, and the same exclusion for procedural-step extraction.
682/682 tests pass; mutation-lab kill rate stayed 6/6 (no surviving
mutants introduced). See `src/crucible/compiler.py` and
`tests/test_compiler_contract.py`.

## Finding 0b (CONFIRMED BY INDUCTION): the check-extraction "starter verb" list had drifted from the canonical oracle-verb list

Spot-checking `REQUIREMENT_WITHOUT_CHECK` found a second, independent
compiler bug, same family as Finding 0 (a mismatch between two things
meant to describe the same concept) but in a different function.

**Root cause**: `_VERIFICATION_STARTER` (decides whether a line of prose
becomes a check at all) matched only 7 verbs (`verify, check, test,
assert, confirm, demonstrate, prove`). `_ORACLE_PATTERNS`'s "command" rule
(decides, for a check that already exists, how it's verified) matched 13
verbs — ADR-0015 fixed that exact 13-verb list as canonical. The two were
clearly meant to be the same vocabulary, but `_VERIFICATION_STARTER`
predated ADR-0015 and was never updated to match it: a line starting with
`run`, `query`, `inspect`, `does`, `ensure`, or `validate` — each already
an accepted command-oracle verb — could never become a check in the first
place, so it could never even reach oracle_kind classification.

**Measured**: `building-detection-rules-with-sigma` has one normative rule
("Validate false positive rate by running against 7 days of production
data...") and was flagged REQUIREMENT_WITHOUT_CHECK — but the skill does
have real, checkable content; "validate" just wasn't in the starter list.
Scanning all 70 (pre-fix) REQUIREMENT_WITHOUT_CHECK findings for a line
starting with one of the six missing verbs found **36/70 (51%)** had this
exact shape.

**Fix**: both lists now come from one shared tuple
(`_VERIFICATION_VERBS`), so they cannot drift apart again. Verified by
induction: re-compiling the Sigma skill now extracts the check with
`oracle_kind: command`. One existing test
(`test_verification_starter_outside_checks_section`) had a fixture line
("Run the analysis.") deliberately chosen to *not* match the old 7-verb
list, used to assert the negative case — it now correctly becomes a check
too, and the test was updated to assert that instead of silently loosened.
A new regression test exercises all six previously-missing verbs
explicitly. 683/683 tests pass; mutation-lab kill rate held 6/6.

## Variant analysis: sweeping for siblings of the Finding 0/0b pattern

Findings 0 and 0b share one shape: two things meant to encode the same
concept (a heading vs. code-fence exclusion; two verb vocabularies) had
drifted apart independently, with no single source of truth forcing them
to agree. Per the `variant-analysis` skill, that shape — not the specific
bug — is the real lead. Before moving to a new finding class, every
top-level vocabulary/pattern constant in `compiler.py` and `auditor.py`
was enumerated and checked for a sibling it should agree with but might
not.

**Confirmed and fixed**: `_ACTION_VERBS` (decides whether a prose bullet
outside a procedural section is a step) independently duplicates every
verb in `_VERIFICATION_VERBS` (validate/verify/check/test/assert/confirm/
demonstrate/prove/inspect/run) by value, not by reference. A bullet like
"- Validate the configuration file before deployment." was extracted as
**both** a check (by `_extract_checks`) and a step (by
`_extract_procedural_steps`) — on **250/818 (31%)** of this corpus. Unlike
the other two candidates below, this one has an explicit, already-written
precedence claim in the code itself ("Bullets in Checks or Verification
sections are skipped — those are checks, not steps"), just never extended
from section-scoped to line-scoped. Fixed: a line already matching
`_VERIFICATION_STARTER` is excluded from step extraction, the same
precedence now applied uniformly. Verified by induction (the motivating
bullet now counts once, as a check only); two new regression tests (the
fix, and that a genuine non-verification action verb like "Deploy" still
becomes a step). 685/685 tests pass; mutation-lab kill rate held 6/6.

**Reviewed, evidence too weak to fix**: `_ACTION_VERBS` also duplicates
every verb in `_NORMATIVE_IMPERATIVE_VERBS` (enforce/require/ensure/
maintain/preserve/protect/guard/isolate/contain/limit/restrict/constrain/
bound/avoid/prevent/pin/seal/guarantee), raising the same hypothesis for
rules vs. steps. Measured: only **1/818** skills would gain a
`METHODOLOGICAL_VACUITY` finding if this were "fixed" the same way.
Reading that one case
(`implementing-network-segmentation-for-ot`, "Rollback plan approved by
operations management") showed a *different* root cause: this is a
prerequisites-checklist noun phrase ("a rollback plan that is approved"),
not an imperative instruction — `_ACTION_VERBS` matched the bare first
word "Rollback" with no part-of-speech awareness at all. Unlike the
check/step case, there is no existing claim anywhere in the codebase that
a rule and a step must be mutually exclusive (a rule phrased
imperatively can legitimately also describe an action). Per this
project's own refutation discipline, n=1 plus a weaker, different-shaped
root cause does not justify a speculative fix; not implemented, recorded
here as a discarded vector instead.

**Reviewed, evidence points the other way**: `_ABSOLUTE_MODALITIES` (gates
`OVERCLAIM`/overgeneralization) includes `MUST`, `MUST_NOT`, `NEVER`,
`ALWAYS` but not `IMPERATIVE` — the same shape of question (a vocabulary
set that might have missed a sibling added later). Checked git history:
the commit that added `IMPERATIVE`-modality extraction (`0b90dc9`, L9)
predates the commit that defined `_ABSOLUTE_MODALITIES` (`539b5d9`) — so
`IMPERATIVE` already existed when the set was written, and that same
commit's own code comment shows explicit awareness of non-RFC-2119
modalities (it special-cases their empty `subject` field a few lines
away). The simpler, better-supported hypothesis is deliberate scoping
(an "Ensure X" instruction isn't judged to carry the same universal-claim
semantics as "X MUST"), not an oversight. Not changed.

| Candidate | Prevalence | Disposition | Why |
|---|---|---|---|
| `_ACTION_VERBS` / `_VERIFICATION_VERBS` (check vs. step) | 250/818 (31%) | **Fixed** | Explicit existing precedence claim in the code; high prevalence |
| `_ACTION_VERBS` / `_NORMATIVE_IMPERATIVE_VERBS` (rule vs. step) | 1/818 | **Deferred, not fixed** | n=1; real root cause is POS ambiguity, not vocabulary drift |
| `_ABSOLUTE_MODALITIES` missing `IMPERATIVE` | n/a (scope question, not a count) | **Not a bug** | Git history supports deliberate scoping over oversight |

This is why every finding count below is reported post-every-fix found
this session (two compiler bugs plus this variant-analysis fix); all
earlier audit passes (committed 2026-10-02) are superseded and should not
be cited as the corpus's real finding distribution.

## Audit: 443 findings across 818 real skills (post all three compiler fixes)

```
CHECK_WITHOUT_ORACLE            27   (91 before Finding 0; unchanged since)
CLAIM_WITHOUT_PROVENANCE         3
DESCRIPTION_BODY_GAP           177   (179 -> 188 -> 177 across the two prior fixes; unchanged by this one)
IRREVERSIBLE_WITHOUT_REVIEW     49
METHODOLOGICAL_VACUITY           1
MISSING_FAILURE_MODE            53   (55 before this fix)
NON_DETERMINISTIC_INSTRUCTION   19   (20 before this fix)
OVERCLAIM                        1
REQUIREMENT_WITHOUT_CHECK       34   (70 before Finding 0b -- 51% was that bug)
SCOPE_TRIGGER_MISMATCH          54
SECRET_IN_OUTPUT                 1
SEMANTIC_REDUNDANCY              1
UNBOUNDED_RESOURCE               1
UNBOUNDED_RETRY                  4
UNPINNED_DEPENDENCY             16
UNVALIDATED_EXTERNAL_INPUT       2
```

All `CANDIDATE` (none of this corpus's skills compose with each other or
self-reference, so no natively-`CONFIRMED` findings exist). Full audit
artifact: `audit.json` in this directory (overwritten after each fix;
earlier versions are recoverable from this file's git history for
comparison). Compile+audit over all 818 skills takes ~3.4s.

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

`DESCRIPTION_BODY_GAP` is the single largest category (177/446, 40%). Its
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

**Quantified 2026-10-02: 177/177 (100%) of DESCRIPTION_BODY_GAP hits on
this corpus are this false-positive pattern. Zero are genuinely thin.**

Method: for every flagged skill, count Markdown section headings in the
body beyond the corpus's universal boilerplate (`Overview`, `When to Use`,
`Prerequisites`, `References`, `Key Concepts` — present in nearly every
skill regardless of quality) and separately count `### Step N:`-style
headings. A skill counts as "structured" if it has either >=2 non-
boilerplate content sections (e.g. `Running Hindsight`, `Key Artifact
Files`, `Validation Criteria`) or >=2 numbered Step sections.

| Classification | Count |
|---|---|
| Structured (procedural/workflow content, false positive) | 177 |
| Genuinely thin (<300 chars of body, no real content) | 0 |
| Unclassified / needs individual review | 0 |

First pass used a narrower rule (Step headings + a fenced code block) and
left 34 skills unclassified; manually reading several of those (e.g.
`analyzing-browser-forensics-with-hindsight`, 10KB body with Prerequisites,
a browser-profile-path reference table, a `## Running Hindsight` section
with real CLI examples) showed they were structured too, just organized
around domain-specific headings instead of `Step N:` — the classifier was
too narrow, not the underlying finding. Broadening to "any 2+ non-
boilerplate headings" (not just Step-shaped ones) closed the gap to 0
unclassified. Full per-skill classification saved in this directory
(`dbg_classification.json`) for independent review.

**Root cause, stated precisely**: `_check_description_body_gap` in
`auditor.py` only treats RFC-2119 modals (MUST/SHOULD/MAY) and a narrow
set of imperative/absoluteness starters as "normative structure." This
corpus's dominant style — numbered `### Step N:` procedures, reference
tables, runnable code blocks, a `Validation Criteria` checklist — carries
real, auditable structure that a human or an LLM would immediately
recognize as substantive, but none of it is phrased with RFC-2119
vocabulary, so the L1 extractor sees it as empty every time. This is **the
concrete gap behind Anna's original framing** ("categories that look fine
but could be grouped/rewritten/improved") — not a bug in the check's logic
(it is accurately reporting "no RFC-2119 structure found"), but a scope gap
in what L1 recognizes as structure at all.

**Engineering proposal (not yet implemented)**: before touching L1's
extractor, decide whether DESCRIPTION_BODY_GAP should (a) stay scoped
exactly as documented — a strict RFC-2119-structure check, with the
corpus-level false-positive rate documented as a known limitation of
*this check against this style of corpus*, or (b) be extended with a
second, independently-justified structural signal (numbered steps /
section headings beyond boilerplate / fenced code blocks) that promotes a
skill out of CANDIDATE when it has real procedural structure the current
extractor can't see. Option (b) is the more useful fix but changes what
the check means; it should not be done as a quiet patch to the existing
rule. Recommend raising this as its own decision record before writing
code, same discipline as this project's existing `docs/decisions/` entries
for L2/L10.

## Not yet done

- Deciding and implementing the DESCRIPTION_BODY_GAP scope/extension
  question above.
- `REQUIREMENT_WITHOUT_CHECK` investigated (Finding 0b above): turned out
  to be a second real compiler bug (verb-list drift), not a calibration
  question, and is now fixed — 70 -> 34. Remaining 34 not yet individually
  classified as genuine gaps vs. a different false-positive pattern.
- Spot-checking the remaining large finding classes (`MISSING_FAILURE_MODE`
  53, `SCOPE_TRIGGER_MISMATCH` 54, `CHECK_WITHOUT_ORACLE` 27, and the
  remaining 34 `REQUIREMENT_WITHOUT_CHECK`) for the same kind of
  style-driven false positive or compiler bug. Given that two of the first
  three categories checked this way turned out to be real compiler bugs,
  not calibration questions, this is a high-value check, not a formality.
- The variant-analysis sweep above covered `compiler.py` and `auditor.py`'s
  top-level vocabulary/pattern constants; it did not exhaustively check
  every other kind of "two things meant to agree" shape (e.g. docstrings
  claiming behavior the code doesn't match, section-range exclusions
  outside the ones already touched). A second, differently-scoped sweep
  could still find more.
- Running L2.5/L12 confirmation and L15 recommendation/narration against
  this corpus (would cost real Nebius calls across potentially hundreds of
  candidates; not run here).
- A licensing decision for using this corpus as the public demo (noted
  as open in `docs/STATUS_AND_TODO.md`).

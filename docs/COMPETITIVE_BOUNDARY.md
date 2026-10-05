# Competitive Boundary and Evidence Map

**Status:** research snapshot  
**Access date:** 2026-09-23  
**Purpose:** prevent CRUCIBLE from claiming a differentiator that current NVIDIA tooling already provides.

## Executive conclusion

CRUCIBLE is not a replacement for NVIDIA SkillSpector or SkillEvaluator. Current NVIDIA tooling already covers a substantial and valuable part of the lifecycle:

- SkillSpector scans for security and supply-chain risk across static, semantic, AST, taint, YARA, and MCP-oriented analyzers.
- SkillEvaluator provides Tier 1 validation/quality/security gates, Tier 2 semantic overlap and deduplication, and Tier 3 live agent evaluation with and without a skill.
- The NVIDIA skills catalog adds publication governance: Skill Cards, detached signatures, Tier-3 evaluation datasets, benchmark reports, and sync-time compliance gates.

The surviving CRUCIBLE boundary is narrower:

> **Compile declared methodology into evidence-bearing structures, analyze typed conditional composition, and test the verifier itself against seeded methodology mutations.**

This is a proposed boundary, not yet a demonstrated product result.

## Capability matrix

| CRUCIBLE capability | SkillSpector | SkillEvaluator | NVIDIA catalog / Verified Skills | Current classification | Consequence |
|---|---|---|---|---|---|
| Schema validation | No primary focus | Tier 1 | Publication gates | FULL OVERLAP | Do not market |
| Security scanning | Primary capability | Integrated/consumed | Required pipeline input | FULL OVERLAP | Complement only |
| Prompt injection / exfiltration | Explicit patterns/analyzers | Security validation | Catalog gate | FULL OVERLAP | Out of primary scope |
| Supply-chain and artifact integrity | Strong coverage | Validates scanner output | Signing and sync gates | FULL OVERLAP | Consume as neighboring evidence |
| Quality gates | Some semantic quality analysis | Tier 1 | Skill Card and benchmark | FULL OVERLAP | Do not call this unique |
| Semantic overlap | Not primary | Tier 2 | Catalog-level artifacts | FULL OVERLAP / PARTIAL | CRUCIBLE needs typed meaning, not cosine labels |
| Redundancy | Not primary | Deduplication and overlap | Not the stated catalog purpose | PARTIAL OVERLAP | Define redundancy by decision/scope/check |
| Synthetic evaluation generation | Not primary | Tier 3 dataset generation | Published datasets | FULL OVERLAP | Use only for differential experiments |
| Live agent comparison | Not primary | Tier 3 baseline vs skill | Benchmark reports | FULL OVERLAP | Do not claim to invent A/B evaluation |
| Provenance | Scan/report provenance | Run/evaluation provenance | Skill Cards, source metadata, signatures | PARTIAL OVERLAP | CRUCIBLE provenance means claim→source/check, not publisher identity |
| Signing | Not primary | Artifact/result provenance | Detached OMS signatures | FULL OVERLAP | Integrity is not semantic truth |
| Normative rule extraction | No evidence found in inspected scope | No evidence found in inspected scope | Skill Cards expose governance metadata, not a rule IR | VERIFIED DIFFERENTIATOR, implementation pending | Candidate core boundary |
| MUST/MUST NOT/SHOULD semantics | No evidence found | No evidence found | Not documented as a corpus analysis | VERIFIED DIFFERENTIATOR, implementation pending | Need conservative parser and source spans |
| Conditions and exceptions | Security pattern conditions exist | Eval assertions/configuration exist | Not a methodology composition model | PARTIAL / UNKNOWN | Must prove with fixtures |
| Requirement → check mapping | No evidence found | Task assertions are not skill-rule coverage | Benchmark metadata is not this mapping | VERIFIED DIFFERENTIATOR, implementation pending | Define explicit oracles |
| Typed composition | Security-relevant relations exist | Group mode stages companion skills | Catalog has source/sync relations | PARTIAL OVERLAP | Separate redundancy/composition/reinforcement/contradiction |
| Conditional contradiction | Security-only overlap may catch subsets | Not found as a general methodology engine | Not found | UNKNOWN / NEEDS EXPERIMENT | Do not claim until benchmarked |
| Invariant representation | Not found as methodology IR | Not found as methodology IR | Behavioral boundaries are metadata, not proof | UNKNOWN / NEEDS EXPERIMENT | Candidate research question |
| Mutation testing of methodology | Not found | Not found | Not found | VERIFIED DIFFERENTIATOR, implementation pending | Central self-test |
| Mutation kill rate | Not found | Not found as methodology metric | Not found | VERIFIED DIFFERENTIATOR, implementation pending | Requires hidden ground truth |
| Seeded defect ground truth | Security test fixtures exist | Eval datasets exist | Published evaluation datasets | PARTIAL OVERLAP | CRUCIBLE needs methodology-specific labels |
| Repair verification | Suggestions/workflows exist | Reports suggest improvements | Publication workflow exists | UNKNOWN / NEEDS EXPERIMENT | Re-audit and replay, never suggestion alone |
| Corpus-level methodology analysis | Security/report aggregation exists | Collection dedup/evaluation exists | Catalog sync exists | PARTIAL OVERLAP | The claim must be about declared methodology semantics |

## Broader community landscape (RU/ZH + general OSS, verified 2026-10-04/05)

The matrix above is scoped to NVIDIA's own tooling. A separate pass
checked whether the broader Agent-Skills community (Russian Habr,
Chinese Juejin/CSDN/cnblogs/oschina/SegmentFault/Zhihu engineering
writing, plus the ~300 tools linked from a widely-shared Russian
"Claude Code Handbook" link-dump) has independently built the same
boundary. Full method and evidence:
`docs/evidence/2026-10-04-ru-zh-corpus-sweep/FINDINGS.md`.

Every claim below is backed by reading the named project's own README
directly (`gh repo view` or a direct fetch), not by trusting a citing
article's paraphrase of it.

| Axis | Representative project(s) | What it actually measures | Overlaps CRUCIBLE's core boundary? |
|---|---|---|---|
| Usage/telemetry audit | `sfrangulov/skill-graveyard` (+ companions `mcp-graveyard`, `memory-graveyard`) | Parses local session logs; buckets each skill as Active/Dead/Missing/Hallucinated | No — measures whether a skill is *used*, never whether its methodology is coherent |
| Install-time security scanning | `rolecraft-sh/rolecraft`, `scalefocus/skilly`, `anthropics/claude-code-security-review`, `trailofbits/skills`, Snyk `agent-scan`/`skill-scan`, skills.sh Trust Hub/Socket badges | Malware, secret leakage, static heuristic risk patterns, before/at install or in a PR diff | No — measures whether a skill is *malicious or leaky*, never whether its stated procedure has a verifiable oracle, a bounded retry, a failure mode, etc. |
| Agent-infrastructure engineering discipline | PGK Digital's "Как не дать проекту деградировать" (Habr) | Practitioner heuristics for Claude Code project hygiene (hooks over prompt rules, memory files, style-audit gates) | No — operational advice for one project's setup, not a corpus-level audit tool; but independently arrives at the same "encode rules into infrastructure, not the prompt" thesis CRUCIBLE is built on, and at a crisp Skill-vs-Rules test ("can you say 'run X and tell me what you got'?") that matches what `DESCRIPTION_BODY_GAP`/`METHODOLOGICAL_VACUITY` try to detect mechanically |
| Deterministic methodology-quality audit with epistemic states + mutation testing | **None found** | — | This is CRUCIBLE's actual boundary, confirmed unoccupied at the scale searched, not merely unsearched |

One correction from an earlier draft: `agentskills.io` is the Agent
Skills *format specification's* own homepage (a client-adoption
showcase), not a registry and not a validator of any kind — it makes
no quality or security claim at all.

A concrete, worth-citing parallel: `skill-graveyard`'s "Hallucinated"
bucket (the agent invokes a skill/tool name that does not resolve) is
the same shape as CRUCIBLE's `BROKEN_REFERENCE`, caught at runtime via
session logs instead of statically via the compiled IR — a genuinely
complementary tool, not a competing one, worth naming as such rather
than ignoring.

Two open scope questions surfaced by CRUCIBLE's own held-out-corpus
audits (does "unpinned dependency = defect" depend on production vs.
ad hoc operational context; does an environment variable count as
untrusted external input) were swept against this same RU/ZH corpus
specifically. Negative, registrable result: neither ecosystem
formalizes the context-vs-pattern distinction as a checkable oracle —
"pin always," "env var is the secrets solution" are universal advice,
never a conditioned rule. This confirms the gap CRUCIBLE's own
`UNPINNED_DEPENDENCY`/`UNVALIDATED_EXTERNAL_INPUT` checks are
grappling with is a real, unsolved problem in the wider ecosystem, not
an artifact of CRUCIBLE's own corpus choice.

## Source-backed observations

### NVIDIA SkillSpector

The repository describes 71 vulnerability patterns across 17 categories, including prompt injection, data exfiltration, privilege escalation, supply chain, excessive agency, output handling, memory poisoning, tool misuse, dangerous code, taint tracking, YARA, MCP least privilege, and MCP tool poisoning. It supports static analysis plus optional LLM semantic analysis and emits multiple report formats.

Source: [NVIDIA/SkillSpector](https://github.com/NVIDIA/SkillSpector), accessed 2026-09-23.

### NVIDIA SkillEvaluator

The current repository describes a multi-tier framework: validation and quality/security gates, semantic overlap/deduplication, synthetic evaluation dataset generation, and live agent evaluation that measures skill impact. Its Tier 3 documentation describes with-skill versus without-skill runs for agents including Codex, Claude Code, and OpenCode, using the same evaluation cases and sandboxed execution.

Source: [NVIDIA/SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator), accessed 2026-09-23. The inspected checkout was `5c73273`.

### NVIDIA Skills catalog

The catalog states that published skills carry `SKILL.md`, `skill-card.md`, `skill.oms.sig`, a Tier-3 evaluation dataset, and `BENCHMARK.md`. It also documents daily mirroring, security scanning, signing, universal evaluation criteria, skill metadata, and sync-time compliance gates.

Sources: [NVIDIA/skills](https://github.com/nvidia/skills) and [signed skill verification](https://github.com/nvidia/skills/blob/main/docs/signing-agent-skills.mdx), accessed 2026-09-23.

## Claim discipline

The matrix distinguishes what the source documents establish from what CRUCIBLE intends to test. In particular:

- “No evidence found” means no corresponding capability was found in the inspected repository/docs scope; it is not proof that NVIDIA has no private or newly added implementation.
- “Verified differentiator” means a boundary supported by inspected public documentation, not an implemented CRUCIBLE result.
- A passing NVIDIA pipeline is evidence about NVIDIA's criteria, not ground truth that a skill is universally coherent.

## Corpus plan

| Corpus | Ground truth | Purpose | Current status |
|---|---:|---|---|
| Author's real skills | Partial | Real composition pressure and regression/reference | PLANNED |
| CRUCIBLE seeded mutants | Yes | Precision, recall, mutation kill rate | PLANNED |
| Independent OSS skills | Unknown | External validity and false-positive pressure | PLANNED |
| NVIDIA verified skills | No universal truth | First-party interoperability and false-positive pressure | PLANNED |

The NVIDIA corpus must not be framed as “clean ground truth.” A signature proves the signed directory identity; a benchmark records an evaluation; neither proves universal methodological correctness.

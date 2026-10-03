# Research Sources

Research snapshot: 2026-09-23. URLs below are primary sources used to bound the project narrative.

| Source | What it establishes |
|---|---|
| [Nebius x NVIDIA hackathon overview](https://nebiusglobalaihackathon.devpost.com/) | Working application, Nebius runtime, NVIDIA open-source model, tracks, submission materials, demo and repository expectations. |
| [Official hackathon rules](https://nebiusglobalaihackathon.devpost.com/rules) | Runtime definition, four tracks, submission period, English/materials, public testing, IP and pre-existing project conditions. |
| [NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector) | Security scanner scope and documented analyzer categories. |
| [NVIDIA SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator) | Tiered validation, overlap/deduplication, synthetic dataset generation, and live agent evaluation. |
| [NVIDIA skills catalog](https://github.com/nvidia/skills) | Catalog governance, daily sync, Skill Cards, signatures, Tier-3 dataset and benchmark artifacts. |
| [NVIDIA signed skill verification](https://github.com/nvidia/skills/blob/main/docs/signing-agent-skills.mdx) | What detached signatures establish and do not establish; signing position in the pipeline. |

## Engineering inspiration (Habr)

Research snapshot: 2026-10-02/03. Secondary sources, not primary hackathon
material: practitioner write-ups (in Russian) that motivated specific
checks or design choices. Credited per concrete change, not as general
background reading.

| Source | What it motivated |
|---|---|
| [Скилл для ИИ-агента: как превратить пожелание в правило](https://habr.com/ru/articles/1066212/) | `COMMAND_ORACLE_WITHOUT_ARTIFACT` (L2, check 29): "any instruction a machine cannot verify, the agent eventually violates without anyone noticing" — the article's argument for shipping an executable validation script alongside a skill rule, not just verification prose. |

More articles from this batch are under review for further checks
(CI gate triage policy, L15 narrator confidence calibration); this table
will grow as each one is actually acted on, not as a reading list.

## Source-handling note

The documents distinguish source-backed facts, local code inspection, intended architecture, and open hypotheses. “Not found” in a public repository inspection is not a proof of non-existence elsewhere. Any future competitive claim must be updated against the then-current upstream HEADs.

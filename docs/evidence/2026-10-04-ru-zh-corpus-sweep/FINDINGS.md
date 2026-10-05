# External corpus sweep (RU + ZH): the context-vs-pattern distinction exists as editorial intuition, not as a mechanism

**Date:** 2026-10-04
**Scope:** external corpus sweep across Russian (Habr) and Chinese
(Juejin, CSDN, cnblogs, oschina, SegmentFault, Zhihu) engineering
writing, against the two open research questions left by the
held-out audits:
`2026-10-04-unpinned-dependency-audit` and
`2026-10-04-unvalidated-external-input-audit`.

**Questions swept:**

- **Q1 — UNPINNED_DEPENDENCY.** Is "unpinned = defect" judged
  lexically, or does any source formalize the operational context
  (production build vs ad hoc helper) as part of the criterion?
- **Q2 — UNVALIDATED_EXTERNAL_INPUT.** Does any source treat an env
  var as a suspect input ("who controls this value?") rather than as
  the recommended channel for operator-controlled secrets?

## Result

**Negative, and registrable:** in the searched corpus, no source
formalizes

```
surface pattern + operational context + trust boundary
+ declared obligation → defect status
```

The dominant treatment is: unpinned = universal bad practice; env var
= preferred secret channel; hook > prompt. The normative distinction
exists scattered as editorial intuition — never as a falsifiable,
checkable rule. Recorded as **"not observed in searched corpus"**,
not as a novelty claim.

## What the corpus did contain

### Q1 — UNPINNED_DEPENDENCY

- **Otus, "8 антипаттернов, из-за которых он падает в проде"
  (2026-06)**: pinning in lockfile + hash verification in CI/CD
  treated as mandatory — *and* a normative rule close to the open
  question: an AI agent with install rights must not install
  dependencies without human review or an allowlist gate. The defect
  status is judged by **operational context** (autonomous agent with
  install privileges), not the lexical pattern — the distinction
  Crucible formalizes, expressed as advice rather than a verifiable
  rule. Same article recommends SBOM and multi-signal verification
  (signatures, verified publisher, version history) over any single
  criterion.
- **NORA** (Kubernetes artifact registry): lockfile-based caching for
  air-gapped environments — the ecosystem assuming the lockfile is
  the reproducibility contract.
- ZH corpus (`依赖锁定`, `锁文件`, `可复现构建`): classic npm
  shrinkwrap / `--save-exact` / yarn.lock / `pip freeze` material;
  `区分生产依赖和开发依赖` — the prod-vs-dev axis exists as advice
  ("distinguish prod deps from dev deps"), never as a checkable
  oracle for when `pip install foo` without a version is a defect.

### Q2 — UNVALIDATED_EXTERNAL_INPUT

- **"Гайд по безопасности вайб-кодинга" (2026-06)**: env vars are the
  *preferred* channel for secrets — "prefer env vars, secret stores,
  or secret files over hardcoded values" — plus short-lived,
  minimal-scope tokens. Nobody in the corpus models "who controls
  this value" as a classifier input.
- **Otus env-vars-in-Node guide**: env validation and typing covered
  as robustness practice, not as trust boundary.
- ZH corpus (`环境变量 安全`, `配置校验 zod`/`envalid`): validate
  config at startup — again robustness framing, not the "who set
  this" question.

### The mother question — pattern vs. normative context

- **PGK Digital, "Как не дать проекту деградировать при работе с
  Claude Code"**: "encode rules into infrastructure, not into the
  prompt" — a hook cannot be forgotten, a CLAUDE.md rule can. The
  `CHECK_WITHOUT_ORACLE` / enforcement-illusion thesis in Russian
  prose.
- **Russian Claude Code handbook (GitHub)**: "verify by fact, not by
  word" — a finding counts as true only when the agent built and
  reproduced the PoC; severity decided by explicit criteria
  (reachability, attacker control, blast radius), not by bug-class
  name. Lists a skill-graveyard auditor and an Agent Skills
  Validator/Security Scanner as direct neighbors.
- **ZH skill-security discussion**: Snyk skill-scan, per-project skill
  isolation, VirusTotal on skills.sh, prompt-injection via SKILL.md —
  active concern, oriented to malware/injection, not to declared-
  methodology audit with epistemic states.

## Interpretation

- The prod-vs-exploratory axis for pinning **exists in both
  ecosystems as advice**, never as a falsifiable oracle. Q1's open
  scope question from the held-out audit is a real gap, not an
  idiosyncrasy of our corpora.
- Q2's "who controls this value" framing is **unrepresented**: env
  vars are uniformly the *solution* side of secrets hygiene.
- Skill security coverage in ZH is oriented to adversarial content
  (injection, malware) — the methodological-audit-with-epistemic-
  states niche remains unoccupied in both corpora searched.

## Queries and anchors (registrable)

RU: `пиннинг зависимостей`, `воспроизводимая сборка`, `lockfile`,
`slopsquatting`, `цепочка поставки ПО`, `переменные окружения
безопасность`, `недоверенный ввод`, `ложные срабатывания статического
анализа`, `аудит скиллов Claude Code`, `evals агентов`.

ZH (掘金/CSDN/cnblogs/oschina/SegmentFault/知乎): `依赖锁定`,
`版本固定`, `锁文件`+`package-lock.json`/`pnpm-lock.yaml`,
`可复现构建`, `区分生产依赖和开发依赖`, `依赖混淆`, `环境变量 安全`,
`密钥管理`, `信任边界`, `污点分析`, `静态分析 误报率`,
`上下文感知 静态分析`, `AI 技能 安全扫描`, `SKILL.md 安全`,
`提示词注入 防御`.

## Addendum 2026-10-05: deeper pass — every article read in full, promising links followed

Anna's direction: "quiero que leas TODOS los artículos y veas si vale la
pena entrar al link... no quiero algo así nomás, tenemos 25 días y todo
el mundo se hace estas preguntas y todo disperso, acordate que lo
estamos haciendo OSS." All 25 files across `habr/1` and `habr/2` read
(the two Chinese files on dependency pinning and SKILL security
re-verified by direct read, not just summarized). Followed every
link that looked like a real competitor or tool, not just cited it.

### The competitive landscape has exactly three occupied axes, and a confirmed-empty fourth

Read `anthropics/claude-code-security-review`, `trailofbits/skills`,
`rolecraft-sh/rolecraft`, `scalefocus/skilly`, `sfrangulov/skill-
graveyard` (the repo Anna named directly), and `agentskills.io` in
full (via `gh repo view` / WebFetch, not just the citing article's
paraphrase):

1. **Usage/telemetry audit** — `skill-graveyard` (sfrangulov, real npm
   package, real stars): parses local Claude Code session logs and
   sorts every skill name into 4 buckets: **Active** (installed +
   invoked), **Dead** (installed, never invoked — removal candidate),
   **Missing** (invoked successfully but no `SKILL.md` found),
   **Hallucinated** (invoked, runtime errored — Claude confused a
   tool/command name for a skill name). Companions: `mcp-graveyard`
   (same model for MCP servers), `memory-graveyard` (same model for
   agent memory files). This is a *usage* axis, not a *content-
   quality* axis — it answers "is this skill used," never "is this
   skill's methodology any good." The **Hallucinated** bucket is worth
   citing: it's the same shape as Crucible's `BROKEN_REFERENCE` (a
   reference to something that does not resolve), just caught at
   runtime via logs instead of statically via the IR.
2. **Install-time security scanning** — `rolecraft` ("static security
   scoring before any skill is installed," 87 agents, 27 verified),
   `scalefocus/skilly` (enterprise self-hosted registry: "every skill
   vetted twice... automatically (malware, secrets, risky-pattern
   scans) and by your own admins," ClamAV + secret detection + static
   heuristics, SCIM 2.0 user lifecycle, hash-chained append-only
   governance audit trail), `anthropics/claude-code-security-review`
   (LLM-based PR diff security review, Anthropic's own), `trailofbits/
   skills` (security-research/audit-workflow skills, not skill
   auditing), the ZH `SKILL安全风险实践` article (prompt injection +
   malicious-script PoC against a real `weather` skill, msfvenom
   reverse shell, DNS-log exfiltration, then lists `skill-defender`,
   Snyk `agent-scan`/`skill-scan`, and skills.sh's Trust
   Hub/Socket/Snyk badges as the detection layer). This axis is about
   *is this skill malicious or does it leak secrets*, never about
   whether its methodology is coherent.
3. **Agent-infrastructure engineering discipline** — the PGK Digital
   article ("Как не дать проекту деградировать...") read in full: its
   sharpest idea is an operational test for *Skill vs Rules*: "if you
   can say 'run X and tell me what you got' — that's a Skill. If it's
   just background knowledge that shapes how the agent writes code —
   that's Rules." That is a crisp, independent articulation of
   exactly the procedural-vs-descriptive distinction Crucible's
   `DESCRIPTION_BODY_GAP`/`METHODOLOGICAL_VACUITY` try to detect
   mechanically — worth citing in Crucible's own docs as outside
   validation that the distinction is real and already recognized by
   practitioners, not an invented category. Same article's "encode
   rules into infrastructure, not into the prompt" (hooks survive;
   CLAUDE.md lines past ~200 get silently ignored) is the same
   deterministic-core-over-LLM-compliance thesis Crucible is built on,
   independently arrived at.
4. **Methodology-quality audit with epistemic states (CONFIRMED/
   CANDIDATE/ABSTAIN) and mutation testing of the methodology itself —
   confirmed empty.** `agentskills.io` is the format spec's own
   homepage (a client-adoption showcase), not a registry and not a
   validator at all -- correcting an earlier mischaracterization.
   None of the ~300 tools linked from the Russian Claude Code Handbook
   link-dump (plugins, subagents, orchestrators, observability
   dashboards, MCP servers, awesome-lists) does this either -- the
   scale of that list (surveyed, not just sampled) is itself
   evidence: an ecosystem this large, searched this broadly, still has
   nobody in this specific niche.

### Other concrete ideas worth citing, not adopting wholesale

- `skill-graveyard`'s `cost` subcommand (estimates token cost of
  installed skill metadata) and `receipt` subcommand (portable,
  privacy-safe skill-use evidence as JSON) are small, good ideas for
  a *companion* tool, not something Crucible should duplicate --
  Crucible's seal is over audit findings, not usage receipts.
- `skilly`'s hash-chained, append-only governance log is the same
  integrity-sealing pattern Crucible/the author's VIGÍA-family
  projects already use, applied to a different object (who-installed-
  what, not methodology findings) -- a good "we're not alone in using
  this pattern" data point, not a feature gap.

### Net effect on positioning

No change to the earlier conclusion (Q1/Q2 open scope questions stand,
no source formalizes the context-vs-pattern distinction as a checkable
oracle). New: a clean three-way differentiation statement is now
directly supportable with named, verified competitors for
`docs/COMPETITIVE_BOUNDARY.md` -- "Crucible audits methodology
quality; `skill-graveyard` audits usage; `rolecraft`/`skilly`/Snyk/
Trail of Bits audit security" -- each claim backed by having actually
read that project's own README, not inferred from a citing article.

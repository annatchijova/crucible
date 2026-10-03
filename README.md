[English](README.md) · [Español](README_ES.md) · **[Technical README](TECHNICAL.md)**

# Crucible

![Crucible logo](visual/logo.png)

A skill can be benign and still teach an agent to engineer badly: retry forever,
require something without checking it, or promise more than its instructions deliver.

Crucible audits agent methodologies and tests its own detector with deliberate
defects. It produces inspectable findings with source evidence, not an opaque
quality score. A candidate finding is a reason to investigate, not proof of a defect.

## See what it detects

This [runnable example](tests/fixtures/readme-demo/SKILL.md) declares an unbounded retry:

```markdown
---
name: retry-example
description: Retry failed operations.
---
Retries MUST continue until success.
```

The audit emits three `CANDIDATE` findings: `UNBOUNDED_RETRY`,
`REQUIREMENT_WITHOUT_CHECK`, and `METHODOLOGICAL_VACUITY`.
The declared obligation has no retry bound or verification check.
The [example contract test](tests/test_readme_contract.py) checks those outputs.

## From a finding to evidence

Crucible compiles skill text into source-addressable records, audits them and
builds a composition graph. Its mutation laboratory deliberately breaks fixtures
to check whether the auditor notices. A behavioral experiment then compares:

```text
same task → no skill / original skill / deliberate mutant / candidate repair
```

The model generates behavior; deterministic property oracles inspect that output.
A repair proposal must pass re-audit and the configured behavioral gate.
One real LLM repair-loop run on the built-in synthetic fixture has been
captured and accepted; this demonstrates the path, not general repair accuracy.
The [private evidence record](docs/REPAIR_EVIDENCE.md) preserves the run's scope
and limitations.

| Question | Evidence Crucible exposes |
|---|---|
| What instruction raised the concern? | Finding status and source evidence |
| Does the detector catch a seeded defect? | Mutation outcome and expected finding |
| Did the skill change observed behavior? | Per-variant property observations |
| Was a proposed repair accepted? | Re-audit and behavioral gate results |

This complements security scanning and agent performance evaluation. Its focus
is methodology and the evidence supporting each claim, not universal skill safety.
See the [comparison scope](docs/COMPETITIVE_BOUNDARY.md) and
[destination architecture](TECHNICAL.md#2-destination-architecture).

## What has been demonstrated

- The local mutation fixture has eight cases: six killed in scope, two abstained
  as out of scope. This is coverage of those fixtures, not recall over all defects.
- A [saved Nebius/Nemotron four-way run](artifacts/nebius/2026-09-30-behavioral-real.json)
  completed without truncation and distinguished the polarity mutant on property P3.
  One run does not establish generalization.
- A real confirmation run completed 14 responses (2 confirmations, 12 rejections),
  but its full artifact was not retained. Model opinions are not ground truth.
  See the [runtime review](docs/red-team/2026-09-30-nebius-runtime-red-team.md).
- The [offline replay storage contract](docs/REPLAY_BUNDLE.md) is implemented.
  The v2 bundle binds captured request/response bytes to the task, skill variants
  and recorded oracle identity under [local tests](tests/test_capture_bundle.py),
  while preserving v1 support. An optional private journal retains committed
  captures across tested process interruptions. The CLI can acquire, inspect and
  export these journals under [local contract tests](tests/test_replay_cli.py).
  Offline oracle replay is implemented and locally verified. One private,
  captured L7 run completed repair, re-audit and behavioral replay on the
  built-in fixture; the [execution checkpoint](docs/NEXT_LEVELS.md) distinguishes
  this demonstration from held-out evaluation and release readiness.

The behavioral experiment uses NVIDIA Nemotron through Nebius Token Factory.
Model observations remain separate from deterministic audit authority; the
[integration contract](docs/NVIDIA_INTEGRATION.md) records the runtime role.
Detailed implementation status is in the [technical level table](TECHNICAL.md#3-construction-levels).

## Run it

Python 3.11 or newer is required.

```bash
pip install -e ".[test]"
PYTHONPATH=src python3 -m crucible.cli tests/fixtures/readme-demo --no-graph
PYTHONPATH=src python3 -m crucible.cli --scan-skill < tests/fixtures/readme-demo/SKILL.md
PYTHONPATH=src python3 -m crucible.cli --report --local-executor > crucible-report.json
PYTHONPATH=src python3 -m crucible.cli --view crucible-report.json > crucible-report.html
PYTHONPATH=src python3 -m crucible.cli --scan-installed --include-coverage
PYTHONPATH=src python3 -m crucible.cli --scan-installed-collection
PYTHONPATH=src python3 -m pytest -q
```

The first command after installation audits the example corpus; the next scans
the same skill through stdin. Without a corpus path, `--report` runs local L4–L7
fixtures; add a corpus path to include L1–L3. Explicit `--local-executor` keeps
confirmation local even if a provider API key exists.

Installed collection scanning audits packages independently, retaining homonymous
skills; it does not evaluate cross-package composition. Partial or empty coverage
exits with code 1. Reader limits and legacy name precedence are documented in the
[technical reader contract](TECHNICAL.md#15-collection-reader-and-known-limitations).

For the local HTTP interface, install its optional dependencies:

```bash
pip install -e ".[api]"
PYTHONPATH=src python3 -m crucible.cli --serve 127.0.0.1:8000
```

This is a local development interface, not a hardened public service.
See [API operations and deployment boundaries](TECHNICAL.md#17-runtime-and-api-operations).

## Repository map

```text
crucible/
├── src/crucible/    # compiler, audit, experiments, repair gates and interfaces
├── tests/          # contract tests, seeded defects and regression fixtures
├── artifacts/      # retained experimental evidence
├── docs/           # execution plan, evaluation, decisions and adversarial reviews
├── README.md       # English introduction and runnable example
├── README_ES.md    # Spanish adaptation with the same scope and commands
└── TECHNICAL.md    # schemas, algorithms, authority boundaries and operations
```

For extending or auditing the system, start with the **[Technical README](TECHNICAL.md)**
and [evaluation plan](docs/EVALUATION_PLAN.md).

## License

Apache-2.0. See [LICENSE](LICENSE).

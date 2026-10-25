# Reproducible demo

Every command below was run on 2026-10-23 at commit `2da823c` and its output
is recorded verbatim. Nothing here needs provider credentials; the one step
that would contact NVIDIA Nemotron is called out and has a deterministic
local substitute.

**Python 3.11 or newer.** Two paths are given: local, which is the shorter
one, and container, which is the one to use for a demo URL.

## Path A — local, deterministic, no credentials

```bash
git clone https://github.com/annatchijova/crucible && cd crucible
pip install -e ".[test]"
```

### 1. What it detects, in one skill

```bash
PYTHONPATH=src python3 -m crucible.cli tests/fixtures/readme-demo --no-graph --human
```

```text
Audit — 3 finding(s)
  [CANDIDATE] METHODOLOGICAL_VACUITY — retry-example
      skill has 1 normative rule(s) but 0 procedural steps and 0 checks
  [CANDIDATE] REQUIREMENT_WITHOUT_CHECK — retry-example
      skill has 1 normative rule(s) but 0 extracted checks
  [CANDIDATE] UNBOUNDED_RETRY — retry-example
      rule rule-0001 contains a retry/repeat indicator without an explicit
      bound (max attempts, timeout, backoff, or circuit breaker)
  7 check(s) abstained on this corpus: BROKEN_REFERENCE, COMPOSITION_CYCLE,
  CONDITIONAL_CONTRADICTION, NORMATIVE_CONFLICT, ORPHAN_SKILL,
  SEMANTIC_REDUNDANCY, SELF_COMPOSITION
  an abstained check found nothing because this corpus supplied no input for it
  digest: sha256:fdc65719e4226d47…
```

The input is four lines of Markdown declaring `Retries MUST continue until
success.` Three findings, each `CANDIDATE` — a reason to inspect, not a
verdict. The abstention block is the part worth pointing at: seven checks
report that this corpus gave them nothing to examine, instead of returning an
empty result that reads as clean.

Drop `--human` for the sealed JSON artifact.

### 2. The detector tested against seeded defects

```bash
PYTHONPATH=src python3 -m crucible.cli --mutate
```

```json
{"by_status": {"ABSTAINED": 2, "KILLED": 6},
 "by_survivor_classification": {"OUT_OF_SCOPE": 2},
 "kill_rate": "6/6", "total": 8}
```

Eight deliberately broken fixtures; six killed in scope, two abstained as out
of scope. This is coverage of those eight fixtures, not recall over defects in
general.

### 3. The closed repair loop

```bash
PYTHONPATH=src python3 -m crucible.cli --repair-loop --local-executor
```

Ends in `"outcome": "ACCEPTED"`: a repair was proposed, the re-audit found the
targeted finding gone with no new findings, and the seeded behavioural
property moved from FAIL to PASS. `--local-executor` keeps this deterministic
and offline. Replace it with provider credentials in `.env` to run the same
loop against Nemotron; one such run is retained privately and described in
[`REPAIR_EVIDENCE.md`](REPAIR_EVIDENCE.md).

### 4. The full pipeline, sealed

```bash
PYTHONPATH=src python3 -m crucible.cli --report --local-executor > crucible-report.json
PYTHONPATH=src python3 -m crucible.cli --view crucible-report.json > crucible-report.html
```

Open `crucible-report.html`. The viewer renders the sealed artifact and
computes nothing of its own.

### 5. Your own installed skills

```bash
PYTHONPATH=src python3 -m crucible.cli --scan-installed --include-coverage
```

Reports `discovered`, `analyzed` and `skipped` so the coverage claim is
checkable. On the development machine this prints a `PARTIAL installed scan`
warning to stderr: 101 analyzed of 299 discovered, 198 skipped as duplicate
packages. Partial coverage is reported, not hidden.

### 6. The test suite

```bash
PYTHONPATH=src python3 -m pytest -q
```

940 tests. A green suite means the contracts hold; it is not evidence about
methodological accuracy on any corpus.

## Optional — the consolidation path, with a real model

Everything above is offline. This one step is not: it needs
`NEBIUS_API_KEY` in `.env` and calls NVIDIA Nemotron.

```bash
PYTHONPATH=src python3 -m crucible.cli <corpus> --confirm        # L2.5, one call per candidate
PYTHONPATH=src python3 -m crucible.cli <corpus> --consolidate    # L16, one call per cluster
```

`--mock-confirm` replaces only the **confirmation** verdict with a
deterministic heuristic, so clustering runs for free. It does not replace the
merge proposer: without credentials `--consolidate` returns
`"outcome": "BLOCKED"` rather than simulating a proposal, which is the same
discipline every other model path in this repository follows. So
`--confirm --mock-confirm` costs nothing, and `--consolidate` costs one call
per cluster whether or not confirmation was mocked.

What it does: the auditor flags two skills as a redundancy candidate, the
model is asked whether they really cover the same ground, connected components
of confirmed pairs become clusters, the model proposes one skill to replace
each cluster, and a deterministic gate accepts or refuses the proposal. The
gate requires that the merge is no longer reported redundant, that every
original rule and check has matching content, and that no finding appears that
the originals did not already have.

**It refuses real proposals.** On a four-skill slice of the sealed `vantaflow`
corpus the gate accepted one merge and refused the other. The refusal turned
out to be a gate defect rather than a bad merge: a corpus-level finding
re-anchored to an untouched skill once the cluster was merged away, and the
gate reads a moved finding as a new one. Both that defect and a second one in
`redundancy_resolved` are recorded in the
[live run record](evidence/2026-10-24-l16-live-real-corpus/FINDINGS.md),
along with a controlled rerun showing the model varies at temperature 0 while
the gate's verdict does not.

Expect about 16 seconds per proposal, and do not expect two runs to agree.

## CLI modes and flags

Detail routed here from the README so the quick path stays short.

| Mode | What it does |
|---|---|
| `<corpus-path>` | compile, audit and build the composition graph |
| `--no-graph` | compile and audit only |
| `--compile-only` | emit the L1 Skill IR, no audit |
| `--human` | render any report as scannable terminal text; an unrecognized shape falls back to JSON unchanged |
| `--scan-skill` | audit one skill read from stdin |
| `--report` | without a corpus path, run the local L4-L7 fixtures; add a corpus path to include L1-L3 |
| `--view <artifact.json>` | render a sealed artifact as self-contained HTML |
| `--local-executor` | keep confirmation local even when a provider API key exists |
| `--skip-duplicate-names` | analyze a corpus that declares a name twice, recording each exclusion |

Installed-skill scanning has two modes and they are mutually exclusive:

- `--scan-installed` audits the installed skills as one corpus. Add
  `--include-coverage` for the `discovered` / `analyzed` / `skipped` counts.
- `--scan-installed-collection` audits packages independently and retains
  homonymous skills. It does **not** evaluate cross-package composition, and
  partial or empty coverage exits with code 1.

Repeat `--scan-root DIR` with either mode to select explicit roots instead of
the standard ones. The HTTP API always uses the standard roots. Reader limits
and legacy name precedence are in the
[technical reader contract](../TECHNICAL.md#15-collection-reader-and-known-limitations).

## Path B — container, for a demo URL

```bash
docker build -t crucible-demo:local .
docker run -d --name crucible-demo -p 8000:8000 \
  -v "$PWD/tests/fixtures:/corpus:ro" crucible-demo:local
```

The build takes about 50 seconds. The volume mount matters: the image copies
only `src/` and `pyproject.toml`, so without it there is no corpus inside the
container to scan by path.

```bash
curl -s http://127.0.0.1:8000/health
# {"status":"ok"}

curl -s -X POST http://127.0.0.1:8000/scan/skill \
  -H 'Content-Type: application/json' \
  -d '{"skill_text":"---\nname: retry-example\ndescription: Retry failed operations.\n---\nRetries MUST continue until success.\n"}'
# 200; audit_version crucible-audit/v2, three CANDIDATE findings

curl -s -X POST http://127.0.0.1:8000/scan/directory \
  -H 'Content-Type: application/json' \
  -d '{"directory":"/corpus/readme-demo"}'
# 200; ir + audit + graph + coverage {"status":"COMPLETE","discovered":1,"analyzed":1}

curl -s http://127.0.0.1:8000/scan/installed
```

`GET /` serves a small HTML page. Interactive API docs are at `/docs`.

A path with no `SKILL.md` returns 400 with
`corpus contains no SKILL.md files: …` rather than an empty success.

**This is a local development interface, not a hardened public service.** Its
data, filesystem, resource and privacy boundaries are described in
[TECHNICAL.md §17](../TECHNICAL.md#17-runtime-and-api-operations) and have not
had their own deployment review. Bind it to localhost.

## What the demo establishes, and what it does not

| Shown | Established | Not established |
|---|---|---|
| Three findings on one skill | the checks fire with source-linked evidence | that these three are real defects; they are `CANDIDATE` |
| Seven abstentions | an unmet precondition is reported, not hidden | that the abstaining checks would be accurate if exercised |
| `kill_rate 6/6` | the detector notices six seeded defects | recall over defects outside those fixtures |
| `outcome ACCEPTED` | the repair gate runs end to end | general repair accuracy; one synthetic task |
| 940 passing tests | the contracts hold | methodological accuracy on any corpus |

Two measurements are deliberately absent because they need human review that
has not happened: the proportion of findings surviving adjudication, and
false negatives. The instruments for both are built, sealed and unlabelled —
see the [adjudication frame](evidence/2026-10-23-adjudication-frame/FINDINGS.md)
and the [false-negative frame](evidence/2026-10-23-false-negative-frame/FINDINGS.md).

A negative result worth stating in any demo: the composition graph produces 86
edges on the author's own corpus and **zero** on all four independently
authored corpora, because an edge requires an author to name another skill.
See the [five-corpus replication](evidence/2026-10-23-heldout-replication/FINDINGS.md).

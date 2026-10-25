# Demo video script — 3 minutes

Shot-by-shot. Every command was run at commit `2da823c` and its output is in
[`DEMO.md`](DEMO.md); nothing in the narration claims more than the retained
evidence supports. Timings total 2:55, leaving margin under the 3:00 cap.

**Setup before recording:** `pip install -e ".[test]"`, terminal at 100x30 or
wider, font large enough to read at 720p, `clear` between shots. No provider
credentials are needed. Record the terminal; the one browser shot is the
viewer HTML opened from a local file.

---

## Shot 1 — the problem (0:00–0:20)

**On screen:** `tests/fixtures/readme-demo/SKILL.md` open in an editor, four
lines visible.

```markdown
---
name: retry-example
description: Retry failed operations.
---
Retries MUST continue until success.
```

**Say:** "This skill is syntactically valid. It has no malicious code and no
exposed secret. A security scanner passes it. And it teaches an agent to retry
forever, with no bound and no way to check the obligation it declares. That is
the category Crucible audits: the quality of the methodology a skill installs
into an agent."

---

## Shot 2 — what it detects (0:20–0:50)

**Command:**

```bash
PYTHONPATH=src python3 -m crucible.cli tests/fixtures/readme-demo --no-graph --human
```

**On screen:** the three findings and the digest line.

**Say:** "Three findings. An unbounded retry, a requirement with no
verification path, and a rule with no steps or checks behind it. Each one is
labelled CANDIDATE — a reason to inspect, not a verdict — and each carries the
instruction it came from. The artifact is sealed with a SHA-256 digest over
canonical bytes, so the same input always produces the same result. No
language model is involved in anything you just saw."

---

## Shot 3 — the part most tools skip (0:50–1:12)

**On screen:** scroll to the abstention block in the same output.

```text
7 check(s) abstained on this corpus: BROKEN_REFERENCE, COMPOSITION_CYCLE,
CONDITIONAL_CONTRADICTION, NORMATIVE_CONFLICT, ORPHAN_SKILL,
SEMANTIC_REDUNDANCY, SELF_COMPOSITION
an abstained check found nothing because this corpus supplied no input for it
```

**Say:** "Seven checks found nothing, and the artifact says why: this corpus
gave them nothing to examine. A check that produced no findings because the
input was absent is not evidence the skill is clean, and until recently this
tool reported those two states identically. Now it separates them."

---

## Shot 4 — testing the detector against itself (1:12–1:38)

**Command:**

```bash
PYTHONPATH=src python3 -m crucible.cli --mutate
```

**On screen:** `"kill_rate": "6/6"`, `KILLED: 6`, `ABSTAINED: 2`.

**Say:** "A detector nobody tests is just an opinion. The mutation lab breaks
eight fixtures deliberately and checks whether the auditor notices. Six killed
in scope, two abstained as out of scope and reported as survivors rather than
quietly counted as passes. This is coverage of eight fixtures — not recall
over defects in general."

---

## Shot 5 — the closed repair loop (1:38–2:05)

**Command:**

```bash
PYTHONPATH=src python3 -m crucible.cli --repair-loop --local-executor
```

**On screen:** scroll to `"outcome": "ACCEPTED"`.

**Say:** "A proposal is not a repair. This loop takes a finding, proposes a
fix, then re-audits deterministically and replays the behavioural property.
Acceptance requires the targeted finding to disappear, no new finding to
appear, and the seeded property to move from fail to pass. The model proposes;
the deterministic gate decides. Swap the proposer for NVIDIA Nemotron and the
wording changes — the verdict and the seal cannot."

---

## Shot 6 — real corpora, and a negative result (2:05–2:32)

**Command:**

```bash
PYTHONPATH=src python3 -m crucible.cli --scan-installed --include-coverage | head -20
```

**On screen:** the `PARTIAL installed scan` stderr line and the coverage
block.

**Say:** "On real corpora it reports coverage, not just findings: 101 analyzed
of 299 discovered, 198 skipped as duplicates. Four external corpora are frozen
by commit and digest, two held back as held-out. On one of them the model ran
the whole chain: it confirmed two skills were the same, proposed a single
skill to replace each pair — and the deterministic gate refused one of them,
because the merge introduced a defect the originals did not have. The model
proposes; the gate decides, and it says no. And one result is worth saying out
loud because it is negative: the composition graph finds 86 edges in my own
corpus and zero in all four written by other people — because an edge requires
an author to name another skill. That is a limit of the tool, measured and
written down, not a feature."

---

**Do not run the consolidation live on camera.** It needs provider
credentials, takes about 16 seconds per proposal, and is not reproducible: the
same cluster at temperature 0 was accepted in one run and refused in another.
Narrate it over the coverage output and cite
[the evidence record](evidence/2026-10-24-l16-live-real-corpus/FINDINGS.md).

---

## Shot 7 — what it does not establish (2:32–2:55)

**On screen:** `crucible-report.html` in a browser, scrolled to the
limitations section.

**Say:** "What this does not establish: that any candidate is a real defect,
or how many real defects it misses. Both need human adjudication, and the
instruments are built, sealed and unlabelled rather than quietly skipped. A
hundred and ninety-two findings are selected for review and twenty-four skills
are set aside for a blind read where the reviewer never sees the tool's
output. Crucible's claim is narrow on purpose: make the methodologies agents
install auditable objects, with the evidence for every claim attached, and the
gaps written down where a reviewer can find them."

---

## Recording notes

- `--human` output fits one screen at 100 columns; the JSON does not. Use
  `--human` on camera.
- Shot 6's `PARTIAL` line goes to **stderr**. Do not redirect stderr away, or
  the most interesting line vanishes.
- Shot 5 takes a few seconds locally. Do not cut mid-run; the point is that it
  completes and the gate decides.
- Avoid `--scan-installed-collection` on camera: its output is about 3.5 MB.
- Do not show `.env`. Nothing in this script needs it.

## Claims deliberately not made

Checked against the reconciliation of 2026-10-23, so the script does not
repeat claims the evidence narrows:

- Not "detects bad methodologies" — it emits candidates for inspection.
- Not "tests composition across skills" — composition is declaration-dependent
  and silent on every third-party corpus measured.
- Not "merges ten skills into one" — batch consolidation is implemented, but
  every measured cluster is a pair and no real corpus connects more than three.
  Say "these two are the same", which is what was demonstrated 337 times.
- Not "no tool does this" — the narrower, supportable claim is that the
  compared NVIDIA tooling does not jointly cover this boundary. See
  [`COMPETITIVE_BOUNDARY.md`](COMPETITIVE_BOUNDARY.md).
- Not "N% accurate" — no precision or recall figure exists yet, by design.

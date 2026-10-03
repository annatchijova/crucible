# ADR-0022: Human-Readable CLI Output (--human)

**Status:** Accepted
**Date:** 2026-10-03
**Reversibility:** high; purely additive -- the existing JSON output is
byte-for-byte unchanged, `--human` is opt-in

## Context

`docs/STATUS_AND_TODO.md`'s P2 item #9 ("TUI pulida") noted that every
`crucible` CLI command prints raw JSON — functional, but not something a
judge, a teammate, or anyone demoing the tool can scan at a glance.

Asked directly how far to take this: a full interactive TUI
(`textual`/`rich`) versus a readable formatter with no new dependency.
The user chose the latter — this project has stayed deliberately
stdlib-only everywhere else (no float libraries, no YAML dependency
beyond `PyYAML` for the one bounded frontmatter subset, no web framework
beyond the optional `fastapi` extra), and a TUI library would be the
first non-optional runtime dependency added purely for presentation.

## Decision

New module `src/crucible/human_output.py`: `format_human(report) -> str`
detects which of the project's report shapes it was given by a handful
of distinctive top-level keys (`audit_digest`+`findings` for an L2
audit, `mutation_digest` for L4, `behavioral_digest` for L5,
`graph_digest` for L3, `confirmation_digest` for L2.5/L12,
`batch_digest` for L16 batch mode, `outcome`+`rejection_reason` shared by
bob/repair-loop/consolidation single-cluster reports), and renders a
scannable terminal summary for each. Anything it does not recognize
falls back to the exact same pretty-printed JSON the non-human path
already produces — `--human` can never be a downgrade; worst case it
looks exactly like today.

Color is plain ANSI escape codes (no library), gated on
`sys.stdout.isatty()` so piped or redirected output is always plain
text — `--human | grep X` or `--human > file.txt` never gets escape
codes mixed into the content.

### CLI wiring

New `--human` flag (`store_true`, default `False` — the usual care after
ADR-0020/0021's "a flag defaulting to something other than `False`/`None`
can look 'set' to the replay-mode mutual-exclusivity check" lesson; this
one is a plain boolean, so it's safe by construction, but it was checked
anyway). Every one of the CLI's ~17 `print(json.dumps(report, ...))`
call sites was replaced by one shared `_emit(data, args.human)` helper —
not 17 separate `if/else` blocks — so the JSON formatting
(`ensure_ascii=False, indent=2, sort_keys=True`) stays defined in exactly
one place and `--human` reaches every command uniformly, including ones
added after this ADR, with no per-flag wiring required.

## Alternatives rejected

- **A real interactive TUI (`textual`/`rich`).** Rejected per direct
  user decision: adds the project's first non-optional runtime
  dependency for presentation alone, and is a materially larger surface
  (navigation, state, terminal capability detection) than what a
  hackathon-scoped "make the output readable" ask needs.
- **Per-command bespoke renderers wired individually at each of the 17
  call sites.** Rejected: one shared `_emit` plus one shape-dispatching
  `format_human` is far less code to maintain and guarantees every
  current and future report type gets `--human` support automatically
  once its shape is added to the dispatcher (or silently falls back to
  JSON if it is not, never crashing).
- **Always render human-readable text, no flag.** Rejected: the CLI's
  JSON output is the project's machine-readable contract (consumed by
  the CI report pipeline, the HTML viewer, replay bundles, and anything
  scripting around this tool); changing the default would be a breaking
  change to every existing consumer for a presentation preference.

## Consequences

Accepted now:
- `src/crucible/human_output.py`, dispatching on 7 known report shapes
  plus a safe JSON fallback for anything else.
- `--human` CLI flag, wired through one shared `_emit` helper replacing
  every raw `print(json.dumps(...))` call site.
- The L5 activation traces from ADR-0021 are immediately visible in this
  renderer (`--behave --human` shows each property's matched keyword and
  snippet inline) — the two features compose for free.
- 13 new falsifiable tests (`test_human_output_contract.py` unit-testing
  the dispatcher and each renderer in isolation;
  `test_human_cli_contract.py` confirming the flag reaches `main()` end
  to end and that omitting it leaves JSON output byte-for-byte
  unaffected). Full suite green, no regressions.

Deferred:
- Rendering for report shapes not yet covered explicitly (e.g.
  `final_report`/L15's combined per-skill report) — these fall back to
  JSON today; adding their own renderer is additive and low-risk
  whenever it's actually needed, not bundled here to keep this increment
  scoped.
- Any interactivity (scrolling, filtering, expanding a finding) --
  explicitly out of scope per the "no new dependency" decision above.

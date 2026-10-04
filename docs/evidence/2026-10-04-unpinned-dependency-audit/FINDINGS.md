# UNPINNED_DEPENDENCY audit: not an extraction bug — an open scope question

**Date:** 2026-10-04
**Context:** continuation of the systematic L2-check held-out audit
(Anna's framing: "pulir que nuestro escanear haga las cosas de manera
coherente"), by held-out hit count. 13 hits across the three held-out
corpora (microsoft-skills, sports-skills, terminalskills).

## What the check does

`_check_unpinned_dependency` (`auditor.py:2903`) fires when a rule or
step matches an install-command pattern (`pip install X`, `npm install
X`, `cargo add X`, `go get X`, `apt install X`, "install the latest",
"use the latest version") with no pinning signal in the same text
(`==version`, `@version`, `pin`, a lock-file name). Its own docstring
states the premise plainly: "No methodology considers floating versions
correct for production."

## Read all 13 in full. Not one shape — a real mix, unlike every mechanism found so far this session

- `azure-ai-language-conversations-py`: "**Always use the latest version**
  of the `azure-ai-language-conversations` SDK." — a clean, textbook
  true positive by the check's own standard: an explicit instruction to
  float, for a production SDK dependency.
- `sentry`: "`npx @sentry/wizard@latest`" — also a clean true positive;
  "@latest" is an explicit, deliberate float.
- `skill-creator` (Rust), two hits: "Use `cargo add` to manage
  dependencies, never edit `Cargo.toml` directly." — likely a **pattern
  false positive**: `cargo add` itself writes a resolved version into
  `Cargo.toml` and regenerates `Cargo.lock` on the next build; the
  instruction is "use the tool that pins correctly," not "install
  without pinning." The check's own `_PINNED_DEPENDENCY_PATTERNS` list
  already recognizes `Cargo.lock` as a pinning signal, but this specific
  text never mentions it, so it isn't credited.
- The remaining 8 (`expense-report`, `lead-qualification`, `msw`,
  `nda-generator`, `pdf-merge-split`, `whisper` x2): ordinary "install
  this library if you don't have it" instructions inside a general-
  purpose coding-assistant skill (e.g. "Install pandas with `pip install
  pandas openpyxl` if not available."). Unpinned by a strict reading,
  but the context is an ad hoc helper script, not a production build or
  deployment pipeline -- the exact context the check's own stated
  rationale ("the build breaks when a new version is released,"
  "production") was written for.

## The open question

This is not an extraction bug like every other mechanism found this
session (no missed heading, no missed conjugation, no title-substring
collision) -- it is a genuine disagreement about **scope**: does "no
methodology considers floating versions correct" hold for a casual,
ad hoc developer-assistant skill the same way it holds for a production
engineering methodology? The check was very plausibly designed against
the latter (mukul975's security/forensics corpus, the author's own
methodology-engineering corpus) and may not transfer cleanly to a corpus
of general-purpose coding-helper skills.

Not resolved here. Anna's direction: document as an open question and
look at how other projects/methodologies in this space have actually
resolved it (e.g. do similar skill-quality or agent-engineering audits
distinguish "production dependency" from "ad hoc script dependency," and
if so, how do they detect the distinction) before deciding whether this
needs a scope carve-out, a severity/context downgrade, or nothing at
all. No code changed.

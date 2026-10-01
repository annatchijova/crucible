# Installed collection review

Base: `2504836`. Scope: the new independent-package collection mode.
Threat model: a local collection author controls package layout and file types;
concurrent filesystem modification during the scan is outside these tests.

Executed tests in `tests/test_installed_collection.py` demonstrate:

- Directory symlink escape: rejected and reported as partial coverage; the
  external skill is not compiled.
- Special file boundary: a FIFO reached the compiler before the fix. A spy
  prevented an actual blocking read. The fix rejects non-regular files before
  invoking the compiler; the test now passes.
- Directory traversal budget: four empty directories bypassed a configured
  two-directory budget before the fix. A counted traversal now rejects the tree.
- Nested homonyms: four distinct source paths, including parent and child skills,
  all produce independent audits and a deterministic collection digest.

Limits: this is not a complete filesystem security audit. Concurrent replacement
between stat and read, ancestor symlinks, per-directory enumeration memory,
aggregate byte budgets, and downstream reference resolution need further review.
The 500-entry guard and 1MB per-skill limit do not bound all traversal costs.
Composition across independent packages is deliberately not evaluated.

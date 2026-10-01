# Installed collection review

Base: `2504836`. Scope: the new independent-package collection mode.
Threat model: a local collection author controls package layout and file types;
the initial tests excluded concurrent filesystem modification. The descriptor
follow-up below adds controlled replacement and growth cases.

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

Initial review limits: concurrent replacement between stat and read and ancestor
symlinks were left for the descriptor follow-up below. Per-directory enumeration
memory and downstream reference resolution still need further review.
This is not a complete filesystem security audit.
The entry, byte and directory limits do not bound all traversal costs.
Composition across independent packages is deliberately not evaluated.

## Follow-up: aggregate budgets

Regression tests reproduced missing aggregate byte accounting and error entries
bypassing the entry limit. Both are fixed: all recorded entries share the cap,
and admitted skill file sizes count toward a 20,000,000-byte budget even if parsing
fails. Equality at the byte boundary is accepted. Files above the individual
1MB limit are rejected without compilation. Whole-scan budget failures propagate
to a CLI JSON ERROR with exit code 1 rather than a traceback.

## Follow-up: descriptor-bound reads

The collection reader now passes its admitted size as an enforced read allowance.
The file is opened nonblocking with O_NOFOLLOW, checked with fstat, and read only
up to its initial size. Size/mtime/ctime changes reject the captured bytes. Parsing
does not reopen the path. Tests cover the exact byte boundary, growth, FIFO and
final-symlink replacement.

Two additional tests initially failed: an ancestor symlink was followed and
replacing the parent just before the final open redirected the read. Opening each
directory relative to a pinned descriptor with O_DIRECTORY|O_NOFOLLOW closes
both tested paths. The replacement test now reads the original pinned directory.

Remaining scope: discovery still uses path-based traversal; legacy corpus reads,
mount changes, hard-link policies and atomic snapshots are not covered by this
reader guarantee. Per-directory enumeration memory remains a separate concern.

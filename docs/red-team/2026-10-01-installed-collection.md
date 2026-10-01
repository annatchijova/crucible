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

Remaining scope at this stage: discovery still uses path-based traversal;
mount changes, hard-link policies and atomic snapshots are not covered by this
reader guarantee. Per-directory enumeration memory remains a separate concern.

## Follow-up: repository compiler shares the bounded reader

The legacy corpus parser used `Path.read_bytes()` without a byte or file-type
boundary. Regression tests intercepted oversized and FIFO reads before actual
I/O; both reached that unsafe call. A third contract test required growth during
descriptor reads to be rejected. All three failed before the shared-reader fix.

Both compiler entry points now use the same bounded byte capture. Six corpus
tests cover oversized input, FIFO, growth, symlink replacement after the precheck,
the exact 1,000,000-byte boundary, and preservation of relative paths and parsed
content. Existing parsing and artifact contracts remain unchanged for admitted
files; oversized files are newly rejected.

Remaining scope at that stage: root resolution still accepts symlink aliases before corpus
discovery, traversal is path-based and materializes matches, and the corpus has
no aggregate byte/traversal budget. Legacy installed-skill staging copies are
not protected by the new reader. No atomic filesystem snapshot is claimed.

## Follow-up: corpus discovery and aggregate budgets

Five pre-fix tests failed: exact and cumulative byte limits, empty-directory
accounting, unrelated-entry accounting, and preservation of a permission error.
The old `rglob` traversal masked that permission error as an empty corpus.

Discovery now streams directory entries with `scandir`, rejects more than
100,000 entries or 10,000 directories (root included), and checks the optional
skill-count cap before sorting admitted paths. The shared reader enforces the
remaining 20,000,000-byte corpus allowance as well as the per-file limit.
Errors abort rather than seal a partial corpus. Additional tests prove early
iterator termination, exact discovery boundaries and failure on an unreadable
subtree even when a readable skill exists.

Remaining scope at that stage: path-based discovery can still race directory replacement;
root aliases and legacy staging copies retain the limitations above. Count and
byte limits do not bound filesystem latency or all downstream analysis costs.

## Follow-up: pinned corpus enumeration

A controlled replacement of the corpus root by a symlink immediately before
`scandir` caused discovery to list an external SKILL.md before the fix. Corpus
enumeration now opens each directory without following symlinks in any component
and calls `scandir(fd)` on the pinned descriptor. Five tests cover the replacement,
descriptor use and closure, injected enumeration errors, queued-child symlink
replacement, and cleanup after budget failure. Existing permission-error tests
now target inode identity so the same assertions apply to descriptor enumeration.

Remaining scope: pending directories and discovered files are still represented
by paths. Reopening rejects symlinks but does not pin identity across all stages;
ordinary-directory replacement, root resolution, mount changes and snapshots are
not covered. Installed-collection discovery and legacy staging remain unchanged.

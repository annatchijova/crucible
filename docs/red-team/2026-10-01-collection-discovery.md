# Independent collection discovery review

Base: `7c531b4`, fix absent. Python 3.12.3 / pytest 9.1.0.
Scope: independent installed-collection traversal and coverage, not semantic audits.

## Threat model and predictions

A local author can populate and replace source paths, but cannot alter Crucible,
the kernel or sealed reports. Test hooks schedule local filesystem operations.
Predictions: unrelated files bypass discovery budgets; a dangling root symlink
and a directory named SKILL.md disappear from error coverage; replacing a file
before compilation is accepted. Rival hypothesis: the bounded reader already
enforces identity from discovery, or existing traversal reports those errors.

## Evidence

CONFIRMED BY INDUCTION under this model: four pre-fix regression tests failed.
The budget did not reject excess unrelated files, invalid roots/entry points
produced EMPTY, and replacement produced COMPLETE. These are resource-bound and
input-selection/coverage defects, not a digest bypass or remote-code execution.

The fix streams bounded enumeration through pinned descriptors, retains directory
and skill identities to reading, and records invalid paths. Directory errors
preserve partial coverage; whole-scan limits propagate. Source-path sorting makes
report ordering independent of enumeration order. Symlinks other than SKILL.md
are now conservatively reported as errors even when they point to non-directories.

Eight tests pass after the fix, including shared/exact budgets, early iterator
termination, permission failure and replacement with a valid neighboring package.
Existing nested homonym, special-file, symlink, digest and aggregate-byte tests
remain green. No additional bypass was demonstrated for those existing controls.

## Reproduction

Run `PYTHONPATH=src python3 -m pytest tests/test_collection_discovery.py -q`.
Fixture identifier: the test file in this commit, SHA-256
`56652745cda84b7fed88fc05486cdc3c37bc0288b063d607352772584bffca1b`.
For the pre-fix state, copy the test file to an isolated checkout of `7c531b4`
and run the first four tests; all four fail. Fixtures use pytest temporary paths.

## Remaining boundaries

Not an atomic snapshot: inode reuse, edits before opening on the same inode,
mount semantics and entries added after enumeration remain outside the guarantee.
Budgets do not impose wall-clock deadlines or bound every downstream analysis cost.
Error messages may contain local paths, consistent with the existing local report.

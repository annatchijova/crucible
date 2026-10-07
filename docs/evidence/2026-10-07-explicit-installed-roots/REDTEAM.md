# Explicit roots for installed direct-child scans

Date: 2026-10-07

## Claim under review

Local Python callers can scan installed skill roots outside the standard home directories while the default scan behavior and public HTTP/CLI surfaces remain unchanged.

## Attack and failure case

The API had no way to select a nonstandard installed root. Tests for a caller-provided root failed with `TypeError` before remediation. Root inputs can also be malformed or dangerous: a scalar path can be mistaken for an iterable, a missing path can look like an empty scan, a symlink can redirect scope, duplicate roots can create misleading duplicate skips, and an unbounded iterable can consume resources before scanning.

## Remediation

`scan_installed_skills(roots=...)` accepts a sequence of explicit roots, validates each without following the final symlink, rejects missing/non-directory/duplicate roots, rejects scalar and empty arguments, and caps the sequence at 256 entries. The selected roots appear in coverage `searched`. Omitting `roots` retains the existing standard-root selection. The HTTP route and CLI do not expose this argument.

## Verification

- Explicit external root selection and coverage reporting: passed.
- Missing, file, symlink, scalar, empty, duplicate, and over-limit roots: rejected by contract tests.
- Legacy installed-scan traversal, identity, staging and API contract tests: passed.
- Full test suite and `git diff --check`: passed.

## Limits

Explicit roots are currently available only to local Python callers of the direct-child installed scan. The independent nested-collection mode, HTTP API, and CLI still use standard roots. This does not discover external plugin caches automatically.

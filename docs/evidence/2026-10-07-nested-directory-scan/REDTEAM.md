# Nested repository directory scan

Date: 2026-10-07

## Claim under review

`scan_directory()` accepts a repository root when its skill packages are nested beneath grouping directories, consistent with `compile_corpus()`'s recursive discovery and the requested directory scope.

## Attack and failure case

The regression fixture creates `repo/group-a/alpha/SKILL.md` and `repo/group-b/beta/SKILL.md`. Before the fix, `scan_directory(repo)` raised `no SKILL.md files found` because `_validate_directory()` checked only immediate child directories. The nested collection scanner found and analyzed both packages. The test therefore went red before the patch.

## Remediation

The shallow skill-presence check was removed from `_validate_directory()`. It still validates the path type, non-empty value, existence, and directory type. `compile_corpus()` now owns recursive, bounded discovery and the empty-corpus rejection, avoiding a second traversal and keeping traversal limits at the compilation boundary.

## Verification

- Nested repository equivalence fixture: directory and independent collection both discover and analyze two packages.
- Existing empty-directory rejection and all API contract tests: passed.
- Full test suite and `git diff --check`: passed.

## Limits

This establishes count agreement for one nested fixture. It does not assert identical audit findings: directory mode audits packages compositionally, while collection mode audits each package independently. Installed direct-child mode has a deliberately narrower scope and is not covered by this equivalence claim.

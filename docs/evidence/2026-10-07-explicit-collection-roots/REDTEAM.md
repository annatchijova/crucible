# Explicit roots for independent collection scans

Date: 2026-10-07

## Claim under review

The independent collection scanner can analyze caller-selected local roots and seal which roots were searched, including when they contain no packages.

## Attack and failure case

Before remediation, `scan_installed_collection(roots=[custom_root])` failed with `TypeError`. Adding roots only as an unsealed runtime option would leave an EMPTY artifact unable to identify the requested scope. Adding `searched` to the existing v1 serialized shape without changing its version would silently alter that artifact contract.

## Remediation

The scanner reuses the explicit-root validator from the direct-child mode. Its collection artifact is now `crucible-installed-collection/v2`; coverage contains the common scope/status/count fields plus `searched`, so the collection digest binds the selected roots. Omitting `roots` preserves standard-root discovery. Historical v1 evidence is not rewritten. The CLI and HTTP route still use defaults and do not accept arbitrary roots.

## Verification

- Nonstandard root with a nested package: analyzed and sealed in the v2 coverage.
- Empty explicit root: returned EMPTY while retaining the searched root in coverage.
- Existing nested-package, partial-error, deterministic digest, traversal, and identity tests: passed.
- Full test suite and `git diff --check`: passed.

## Limits

No reader or migrator for stored collection artifacts is present in this repository; this change only produces v2 artifacts. It does not add root selection to HTTP/CLI or automatic custom Codex-home discovery. Standard discovery behavior and historical v1 artifacts remain unchanged.

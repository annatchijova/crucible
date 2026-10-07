# API scan coverage counts

Date: 2026-10-07

## Claim under review

The uploaded-text and local-directory API paths report common input-accounting fields outside their sealed audit artifacts.

## Attack and failure case

The installed-scan paths reported scope and counts, while `/scan/skill` and `/scan/directory` returned no coverage envelope. A caller could not distinguish an unreported scope from a complete one by using a common response field. Contract tests for both modes failed against the prior implementation with `KeyError: 'coverage'`.

## Remediation

Both API results now return `scope`, `status`, `discovered`, `analyzed`, `skipped`, and `errors` under `coverage`. Uploaded text reports one analyzed input. Directory scanning reports the compiled skill count. Existing audit, IR, and graph fields remain unchanged; the audit digest is not modified by this metadata.

## Verification

- Uploaded-text coverage contract: passed.
- Two-skill directory coverage contract: passed.
- Full test suite: passed.
- `git diff --check`: passed.

## Limits

This does not unify the independently sealed nested-collection envelope, add per-item exclusion reasons to every mode, or prove equivalence for arbitrary corpus layouts. Directory compilation is all-or-error, so partial package errors are not represented as a successful partial result here.

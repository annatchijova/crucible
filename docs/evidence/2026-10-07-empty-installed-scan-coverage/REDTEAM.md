# Empty installed-scan coverage contract

Date: 2026-10-07

## Claim under review

`scan_installed_skills()` reports coverage for its installed direct-child package scope, including when that scope contains no packages. The CLI exposes that additive field only when requested with `--include-coverage`.

## Attack and failure case

Exercise both empty discovery states: no standard skill directory exists, and a standard directory exists but contains no `SKILL.md` package. A consumer using coverage to distinguish an empty scan from an omitted field previously received no coverage object in either state. The CLI's successful-scan opt-in contract also had no corresponding empty-scan result.

The new API and CLI contract tests failed against the prior implementation with `KeyError: 'coverage'` (two API cases and the CLI opt-in case). The no-flag CLI case passed as a compatibility control: it expected the legacy error output without coverage.

## Remediation

The API now returns `status: EMPTY` with zero discovered, analyzed, and skipped counts and an empty item list for both empty states. Its `searched` coverage field represents the standard search roots. Existing error fields remain available. The CLI includes coverage on error only when `--include-coverage` is set; default error JSON retains its previous shape.

## Verification

- Empty API cases and empty CLI opt-in/compatibility cases: passed.
- Installed coverage CLI contract, installed collection, and collection discovery tests: passed.
- `git diff --check`: passed.

## Limits

This closes the empty-result coverage gap for `scan_installed_skills()` only. It does not establish cross-mode coverage equivalence, change collection scanning, or make claims about package contents that were not discovered.

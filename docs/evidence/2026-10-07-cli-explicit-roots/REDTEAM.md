# CLI explicit installed roots

Date: 2026-10-07

## Claim under review

The local CLI can pass repeatable explicit roots to either installed scan mode, while invalid option combinations fail before any scan starts and existing default output remains unchanged.

## Attack and failure case

Before remediation, `--scan-root` was rejected as an unknown option in both modes. Supplying both installed-mode flags was accepted; the collection branch then ran and emitted a large local result instead of rejecting the ambiguous invocation. These failures were reproduced by contract tests before the patch.

## Remediation

Added repeatable `--scan-root DIR`, wired to the explicit-root API for both installed modes. Root selection requires exactly one installed mode and cannot accompany a positional corpus path. The two installed modes are now mutually exclusive. Invalid root errors are emitted as machine-readable JSON with exit code 1; parser misuse exits 2 before invoking a scanner. Calls without `--scan-root` retain existing behavior and JSON shape. No HTTP route accepts these paths.

## Verification

- CLI scan with two explicit roots in direct-child mode: passed.
- CLI scan with two explicit roots in independent-collection mode: passed.
- Invalid/missing roots and invalid mode combinations: rejected before scan or returned as machine-readable errors.
- Existing coverage opt-in/default-output tests: passed.
- Full test suite and `git diff --check`: passed.

## Limits

Explicit roots select local directories only; this does not acquire remote repositories or execute repository scripts. For a repository tree, use the directory-scan mode. HTTP root selection remains unavailable by design.

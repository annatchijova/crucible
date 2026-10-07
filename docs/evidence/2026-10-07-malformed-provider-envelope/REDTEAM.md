# Malformed provider envelope handling

Date: 2026-10-07

## Claim under review

The legacy Nebius executor converts malformed provider response bodies and envelope shapes into explicit error observations. It must not raise a shape-related exception or return malformed usage as trusted metadata.

## Attack and failure case

The response body is external input. Tests injected invalid JSON and UTF-8, a non-object root, a null first choice, a null message, list-shaped usage, and a string token count. Before remediation, five structural probes failed: two escaped as `AttributeError`, one was treated as ordinary non-text content, one escaped while reading usage, and a string token count was returned as if valid. The legacy no-usage behavior remains zero-filled for compatibility.

## Remediation

The executor validates decoded root, choice, message, usage, token counts, and finish reason before projecting the response. Invalid JSON/UTF-8 and invalid structures return an empty output with an `invalid provider response` error. Token counts must be non-negative integers; booleans are rejected as integers. The separate byte-preserving capture path is unchanged and continues to retain raw response bytes as transport evidence.

## Verification

- Malformed envelope tests: passed for eight hostile body/shape cases.
- `tests/test_runtime_capture.py`: passed.

## Limits

This covers the first choice consumed by the current executor and its usage metadata. It does not validate every provider-specific optional field or claim live-provider conformance. Capture receipt remains distinct from parsed-response validity and from behavioral acceptance.

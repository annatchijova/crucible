# R2 executor capture — scoped adversarial review

Base: `45fb66b`, Python 3.12.3. Scope: new opt-in transport capture and the shared
request builder. Method: software archaeology and red-team-auditing. No real
provider call, provider authentication test or R3 replay execution was performed.

## Threat model

The provider may return malformed bytes, missing metadata, HTTP errors, excessive
response bodies or an interrupted stream. Callers may supply empty guidance.
The transport and local implementation are trusted; compromised process memory,
malicious replacement of the code and a malicious author resealing evidence are
outside the integrity claim. Bodies can contain secrets and are private by default.

## Characterization and blast radius

Existing `execute` callers include the behavioral harness, with downstream report
and repair-loop consumers. Their return shape and response normalization remain
unchanged. The only shared change extracts request construction. The new API is
opt-in and performs its own request; it does not retroactively capture old runs.

Before implementation, the characterization test passed: empty system guidance
became the default assistant prompt, and absent usage became zero counts. These
are pinned legacy behaviors, not evidence-correctness claims. Nine new capture
cases failed because the capture API/module did not exist. After implementation,
those cases and the additional interrupted-stream/compatibility probes passed.

## Findings and attempted vectors

| Prediction | Epistemic level and observed result | Resolution/scope |
|---|---|---|
| The actual no-skill request differs from the v1 replay guidance | CONFIRMED BY INDUCTION by the characterization and wire-body tests | Compatibility gap, not a security exploit; retain both strings and defer versioned bundle integration |
| Capturing legacy normalized results would invent absent usage | CONFIRMED BY INDUCTION: legacy result has zero usage while response bytes omit it | Capture raw bytes instead of normalized results |
| Transport receipt could be mistaken for valid model output | FALSIFIED for this API: malformed JSON, invalid UTF-8 and finish_reason=length are retained as RECEIVED, never COMPLETED or accepted | No model verdict exists in capture |
| Authorization or transport-exception text could enter capture | FALSIFIED for injected header/exception fixtures | Only bodies are retained; provider-echoed secrets remain possible and documented |
| Oversized response could be labeled complete | FALSIFIED by bounded-prefix probe | RESPONSE_LIMIT, complete=false, prefix digest |
| Read interruption could discard already observed bytes | FALSIFIED by timeout and IncompleteRead probes | Prefix retained with TRANSPORT_ERROR |
| Capture could silently pass as a replay bundle | FALSIFIED by validator probe | Distinct version rejected by replay validator |
| Extracting the request builder could alter legacy wire input | FALSIFIED for empty guidance and custom model/sampling fixture | Exact request bytes match between legacy and capture paths |

These results are scoped to the executable fixtures, not a global security claim.
Reproduce with:

```bash
PYTHONPATH=src python3 -m pytest tests/test_runtime_capture.py tests/test_behavioral_contract.py tests/test_replay_bundle_contract.py tests/test_readme_contract.py -q
```

## Remaining R2 work

Capture-to-bundle integration must explicitly represent prompt transformation,
retain source/oracle identity and bind observations to captured output. CLI export
is pending. Endpoint identity, redirects and a total wall-clock deadline are not
covered by this capture. Historical artifacts remain untouched. No real provider
evidence or real repair-loop completion is claimed.

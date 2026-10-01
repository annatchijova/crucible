# R2 capture-backed replay v2 review

Base: `114c615`; Python 3.12.3. Scope: capture validation, v2 acquisition and v1/v2
storage compatibility. All provider calls were mocked. No remote run, offline
replay adjudication, durable export or repair acceptance is claimed.

## Threat model and method

The adversary controls imported capture/bundle bytes, may recalculate their seals,
and may provide malformed HTTP bodies/metadata. They do not control local trusted
oracle code. A malicious author replacing an entire experiment and resealing it
is outside authenticity claims: these digests are not signatures.

Skills: versioned-schema-evolution preserves historical v1 interpretation;
software-archaeology keeps existing executor/report behavior unchanged;
red-team-auditing separates schema integrity from evidence truth.

## Predictions and executed results

| Prediction tested | Epistemic result | Evidence |
|---|---|---|
| v2 can preserve empty original guidance and the actual nonempty baseline wire prompt without changing v1 | CONFIRMED BY INDUCTION | v2 round-trip plus unchanged v1 contract suite |
| Resealing alone can hide mismatched task/guidance/wire data | FALSIFIED for tested mutations | Internal links and adapter rules reject them |
| A blocked capture can be resealed into an attempted/received contradiction | FALSIFIED | Status/attempt/response constraints reject the fixtures |
| Missing or truncated runtime metadata can become ready through default values | FALSIFIED | Missing ID/finish/usage, length finish and invalid usage all remain incomplete |
| Invalid JSON/UTF-8 or duplicate keys can acquire valid observations | FALSIFIED | Raw bytes survive; observations remain empty and readiness false |
| A fabricated PASS can be attached to a non-text/error response | FALSIFIED | v2 rejects observations without captured textual output |
| Loading a bundle calls the provider or executes the oracle | FALSIFIED | Fail-on-call guards remain untriggered |
| Oversized accumulation continues making calls and discards the first capture | FALSIFIED for the aggregate-limit fixture | One call; partial evidence retained in a typed exception |
| Mutating caller inputs during acquisition changes the recorded task/variants | FALSIFIED | Deep copies retain the pre-execution inputs |
| Oracle drift during acquisition silently produces a sealed bundle | FALSIFIED | Acquisition stops with partial evidence instead |

The initial 14 integration cases failed before implementation because the API did
not exist. Later negative controls extend that set. These are bounded fixture
results, not general exploitability or security certification.

## Compatibility and limits

Readers keep v1 field/seal semantics. v2 is an explicit new version, not a hidden
migration. Its adapter permits only the existing prompt fallback. Captures and
original source text are both retained; projections cannot silently overwrite them.
The pinned oracle is local source/runtime identity, not loaded-code attestation.
Storage validation does not recompute historical observations or prove them true.

CODE FACT: acquisition remains in memory. Partial-evidence exceptions do not make
it crash-safe; other acquisition failures can still lose completed work. Durable
incremental persistence and CLI export are the next R2 work, before claiming gate
closure. No severity is assigned to a guarantee the API does not yet claim.

## Reproduction

```bash
PYTHONPATH=src python3 -m pytest tests/test_capture_bundle.py tests/test_replay_bundle_contract.py tests/test_runtime_capture.py tests/test_readme_contract.py -q
```

Fixtures live in `tests/test_capture_bundle.py`, using current task/variant
fixtures but never claiming to reconstruct historical real-provider runs.

# R2 private capture journal review

Base: `cfa261a`; Python 3.12.3. Scope: optional incremental retention, recovery
inspection and preservation of the existing non-journal acquisition path.

## Threat model and evidence boundary

Tests inject process termination, projection failure and SQLite transaction
failure. A competing creator may target the same destination. The destination
parent, operating system, filesystem sync behavior and SQLite implementation are
trusted. Hostile imported databases, malicious same-user file replacement and
hardware power-loss behavior are not covered. No provider call was made.

## Executed predictions

| Prediction | Result and epistemic level |
|---|---|
| A process exiting without closing SQLite loses its prior committed capture | FALSIFIED: subprocess exits 17 on the second variant; reopening retains the first capture and reports PARTIAL |
| Projection failure loses the just-returned raw capture | FALSIFIED: capture persists, observations remain null and the variant is listed as unobserved |
| Finalization failure leaves a falsely complete experiment | FALSIFIED: injected SQLite abort rolls back finalization; all four captures remain, bundle absent |
| Checkpoint failure still permits another provider call | FALSIFIED: injected insert failure stops acquisition after one executor invocation |
| Existing or completed journals can be silently overwritten | FALSIFIED for API probes: creation/reuse/second finalization fail and existing data remains |
| Recovery hides changed observation bytes behind the final bundle | FALSIFIED for corruption probe: digest validation rejects inspection |
| Unknown journal versions can be read as current | FALSIFIED: unsupported user_version rejected |

The seven initial journal tests failed before implementation because the journal
API did not exist. The completed probes live in `tests/test_capture_journal.py`;
these are fixture-specific results, not universal durability certification.

## Construction and compatibility

The optional keyword-only journal leaves existing callers on the in-memory path.
Capture and observation checkpoints are distinct so a missing observation cannot
be invented after interruption. Finalization validates and links the saved bundle
within one transaction. The journal never reissues provider requests. COMPLETE is
a persistence state; readiness and acceptance remain separate contracts.

The SQLite transaction pattern follows atomic-state-mutation, with FULL rather
than NORMAL synchronization. The format is explicitly versioned. The private
directory prevents other local users from reading its contents under normal POSIX
permissions; it does not redact secrets echoed into prompt/response bodies.

## Remaining scope

CODE FACT: in-flight responses and data lost before commit cannot be recovered.
CLI acquisition/export and operator-facing recovery remain the next R2 work.
No automatic retry or migration is implemented. Physical power-loss testing and
adversarial filesystem replacement are not claimed.

```bash
PYTHONPATH=src python3 -m pytest tests/test_capture_journal.py tests/test_capture_bundle.py tests/test_replay_bundle_contract.py -q
```

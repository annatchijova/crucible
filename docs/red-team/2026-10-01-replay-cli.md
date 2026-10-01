# R2 journal CLI — scoped review and gate evidence

Base: `db6bca3`; Python 3.12.3. Scope: journal-backed acquisition, offline inspection
and export. All tests mock or prohibit network access. No real provider run or R3
oracle replay is claimed.

## Threat model

The caller may combine conflicting modes, configure a provider key while using an
offline command, select existing/missing/corrupt local journals, or interrupt an
experiment. Provider output may be incomplete or contain private text. Local
journal ownership/filesystem assumptions are inherited from the journal contract;
hostile SQLite databases and compromised local oracle code remain outside scope.

## Predictions and results

| Prediction tested | Epistemic result |
|---|---|
| Inspection/export can select a provider merely because a key exists | FALSIFIED: constructor/network guards remain untriggered |
| Mixed capture/scan/server/report options can start work before rejection | FALSIFIED for eleven flag combinations: exit 2 before creating the journal |
| Blocked/truncated/missing-finish evidence is exported with a success exit | FALSIFIED: preserved complete bundles export exactly, but exit 1 |
| Partial acquisition is silently completed for export | FALSIFIED: inspection reports pending variants; export prints no JSON |
| Normal capture output leaks a response body | FALSIFIED for the marker fixture: summaries contain no body marker |
| Exception text can reveal a credential through diagnostics | FALSIFIED for injected secret-bearing errors and KeyboardInterrupt |
| Existing destinations are overwritten | FALSIFIED: exit 2 before executor activity |
| Missing/corrupt journals are treated as empty valid evidence | FALSIFIED: exit 2; missing paths are not created |

Before implementation, nine positive/operational tests failed because flags were
unknown. Eleven negative flag-combination tests already passed for that reason;
those alone were not evidence of correct routing. After implementation, both
positive paths and rejection cases pass. Recovery persistence itself is also
covered by the prior subprocess-exit and transactional rollback journal tests.

## Gate interpretation

The R2 bounded gate is locally verified for the current four-way Nebius adapter:
frozen task/variant inputs, captured wire evidence, explicit prompt transformation,
oracle identity, journal checkpoints, offline import/export and incomplete-evidence
classification. The complete bundle is exported, not reconstructed from today's
fixtures. Existing v1 readers and old CLI contracts remain supported.

This does not close R3: storage/readiness does not re-run a trusted oracle or
adjudicate repairs. It does not establish provider authenticity, successful real
remote behavior, universal filesystem durability or recovery before a commit.
Those boundaries remain explicit; R3 is the next construction increment.

## Reproduction

```bash
PYTHONPATH=src python3 -m pytest tests/test_replay_cli.py tests/test_capture_journal.py tests/test_capture_bundle.py tests/test_replay_bundle_contract.py -q
```

Export goes to stdout. Protect destination permissions and avoid shell clobbering;
an interrupted output file is not an atomic export, but the source journal remains
available. The CLI reports no acceptance verdict, regardless of exit code.

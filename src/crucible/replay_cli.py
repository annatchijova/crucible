"""Journal CLI boundary: acquisition is explicit; inspection/export stay offline."""

import json
import sys

from .capture_journal import CaptureJournal, read_journal
from .replay import dump_bundle, replay_readiness


def _summary(snapshot):
    readiness = (replay_readiness(snapshot['bundle']) if snapshot['bundle'] is not None
                 else {'evidence_complete': False, 'incomplete_variants': None})
    return {
        'schema_version': 'crucible-replay-cli/v1',
        'status': snapshot['status'],
        'captured_variants': len(snapshot['captures']),
        'pending_variants': snapshot['pending_variants'],
        'unobserved_variants': snapshot['unobserved_variants'],
        **readiness,
    }


def run_replay_command(mode, directory):
    """Exit 0: complete evidence; 1: valid but incomplete; 2: error; 130: interrupt.

    Exit 0 is not a repair verdict. Export preserves valid blocked/error evidence
    with exit 1. Partial acquisition is inspectable, but is never fabricated into
    a replay bundle. Exception text may contain private content and is not echoed.
    """
    if mode not in ('capture_replay', 'inspect_replay', 'export_replay'):
        raise ValueError('unknown replay CLI mode')
    try:
        if mode == 'capture_replay':
            # Imported/constructed only on this branch; offline commands cannot
            # accidentally select an executor from credentials in the environment.
            from .behavioral import NebiusExecutor
            from .capture_bundle import capture_behavioral_bundle

            print('Capturing a new provider experiment. Journal contents are private; no automatic retries.',
                  file=sys.stderr)
            with CaptureJournal(directory) as journal:
                capture_behavioral_bundle(NebiusExecutor(), journal=journal)
        snapshot = read_journal(directory)
        summary = _summary(snapshot)
        if mode == 'export_replay':
            if snapshot['bundle'] is None:
                print('Cannot export: acquisition is empty or partial. Inspect the retained journal; no calls were retried.',
                      file=sys.stderr)
                return 1
            serialized = dump_bundle(snapshot['bundle'])
            print('Export contains private prompts/responses. Protect the destination; evidence completeness is not acceptance.',
                  file=sys.stderr)
            print(serialized)
        else:
            print(json.dumps(summary, sort_keys=True))
        return 0 if summary['evidence_complete'] else 1
    except KeyboardInterrupt:
        print('Interrupted. Inspect any retained journal; an unrecorded response must not be assumed unrequested.',
              file=sys.stderr)
        return 130
    except Exception:
        # A top-level CLI boundary, not a library catch: preserve journal evidence
        # and keep arbitrary provider/filesystem exception content off stdout/stderr.
        print('Replay command failed. Check the path and journal integrity; existing evidence was not retried or replaced.',
              file=sys.stderr)
        return 2

"""Command-line surface for compilation, auditing, composition analysis, mutation testing, behavioral differential, Bob workflow, closed repair loop, report, and viewer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .auditor import audit_corpus
from .behavioral import LocalExecutor, NebiusExecutor, run_behavioral_differential
from .bob import LLMProposer, RuleBasedProposer, run_bob_workflow
from .compiler import compile_corpus
from .confirm import (
    MockConfirmExecutor,
    NebiusConfirmExecutor,
    confirm_candidates,
    confirm_semantic_redundancy,
)
from .consolidation import (
    LLMConsolidationProposer,
    run_consolidation,
    run_consolidation_batch,
)
from .final_report import build_final_report
from .final_report_render import (
    render_final_report_html,
    render_final_report_markdown,
    render_final_report_pdf,
)
from .graph import build_composition_graph
from .human_output import format_human
from .mutation import run_mutation_lab
from .narrator import MockNarrationExecutor, NebiusNarrationExecutor
from .repair_loop import run_repair_loop
from .repair_evidence import run_captured_repair
from .report import run_full_report
from .viewer import render_artifact_html


def _emit(data: Any, human: bool) -> None:
    """Print a report either as human-readable text or as JSON.

    The JSON path is byte-for-byte unchanged from before --human existed
    (same ensure_ascii/indent/sort_keys); --human renders the identical
    data, never a recomputation, through human_output.format_human.
    """
    if human:
        print(format_human(data))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="crucible",
        description="Compile, audit, analyze, mutation-test, behaviorally evaluate, repair, close the loop, report, and view a skill corpus.",
    )
    parser.add_argument(
        "root",
        nargs="?",
        help="directory containing SKILL.md files (required unless --mutate/--behave/--bob/--repair-loop/--report/--view)",
    )
    parser.add_argument(
        "--compile-only",
        action="store_true",
        help="emit the L1 Skill IR without auditing or graph analysis",
    )
    parser.add_argument(
        "--human",
        action="store_true",
        help="render the report as human-readable terminal text instead "
             "of JSON (same report data, no new dependency; falls back "
             "to JSON for any shape it doesn't recognize)",
    )
    parser.add_argument(
        "--no-graph",
        action="store_true",
        help="emit L1 + L2 audit without L3 composition graph",
    )
    parser.add_argument(
        "--mutate",
        action="store_true",
        help="run the L4 mutation lab against the built-in base fixture",
    )
    parser.add_argument(
        "--behave",
        action="store_true",
        help="run the L5 behavioral differential harness",
    )
    parser.add_argument(
        "--local-executor",
        action="store_true",
        help="use the local deterministic executor instead of Nebius (for testing)",
    )
    parser.add_argument(
        "--bob",
        action="store_true",
        help="run the L6 Bob workflow on the first finding",
    )
    parser.add_argument(
        "--repair-loop",
        action="store_true",
        help="run the L7 closed repair loop (find -> repair -> re-audit -> behavioral replay -> accept/reject)",
    )
    parser.add_argument(
        "--repair-evidence",
        metavar="NEW_PRIVATE_DIR",
        help="capture and seal one real --repair-loop run in a new private directory (requires --llm-proposer and Nebius credentials)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="run the full L1-L7 pipeline and emit a sealed composite report",
    )
    parser.add_argument(
        "--view",
        metavar="ARTIFACT_JSON",
        help="render a sealed artifact JSON as a self-contained HTML page",
    )
    parser.add_argument(
        "--llm-proposer",
        action="store_true",
        help="use the LLM proposer (Nemotron via Nebius) instead of rule-based",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="run the L2.5 semantic redundancy confirmation layer on the audit",
    )
    parser.add_argument(
        "--mock-confirm",
        action="store_true",
        help="use the deterministic mock executor for the confirmation layer (for testing)",
    )
    parser.add_argument(
        "--consolidate",
        action="store_true",
        help="run the L16 consolidation workflow: cluster CONFIRMED "
             "SEMANTIC_REDUNDANCY pairs and have an LLM propose one merged "
             "skill per cluster, gated deterministically (no behavioral "
             "check -- see consolidation.py)",
    )
    parser.add_argument(
        "--cluster-index",
        type=int,
        default=None,
        help="which redundancy cluster to consolidate, 0-indexed "
             "(default: 0; used with --consolidate)",
    )
    parser.add_argument(
        "--consolidate-all",
        action="store_true",
        help="run --consolidate over every redundancy cluster in one call, "
             "applying each accepted merge before moving to the next "
             "cluster; a rejected/blocked cluster is left unmerged and "
             "does not block the rest (mutually exclusive with "
             "--consolidate/--cluster-index)",
    )
    parser.add_argument(
        "--narrate",
        action="store_true",
        help="run L2 audit + L2.5 confirmation, compute L15 deterministic "
             "recommendations, and have an LLM narrate each non-KEEP skill",
    )
    parser.add_argument(
        "--mock-narrate",
        action="store_true",
        help="use deterministic mock executors for both confirmation and "
             "narration (for testing; implies --narrate)",
    )
    parser.add_argument(
        "--render-report",
        metavar="FINAL_REPORT_JSON",
        help="render a sealed crucible-final-report/v1 JSON artifact (from "
             "--narrate) as markdown, html, or pdf",
    )
    parser.add_argument(
        "--render-format",
        choices=("markdown", "html", "pdf"),
        default=None,
        help="output format for --render-report (default: markdown)",
    )
    parser.add_argument(
        "--out",
        metavar="FILE",
        help="write --render-report output to FILE instead of stdout "
             "(required for --render-format pdf)",
    )
    parser.add_argument(
        "--scan-skill",
        action="store_true",
        help="scan a single SKILL.md from stdin (L11)",
    )
    parser.add_argument(
        "--scan-installed",
        action="store_true",
        help="scan the user's installed skills (L11)",
    )
    parser.add_argument(
        "--serve",
        metavar="HOST:PORT",
        nargs="?",
        const="127.0.0.1:8000",
        help="start the HTTP API server (L11)",
    )
    parser.add_argument(
        '--include-coverage', action='store_true',
        help='include installed-scan coverage alongside the sealed audit',
    )
    parser.add_argument('--scan-installed-collection', action='store_true',
                        help='audit nested installed packages independently, including homonyms')
    parser.add_argument('--scan-root', action='append', metavar='DIR',
                        help='scan this explicit local root (repeatable; requires one installed scan mode)')
    replay_modes = parser.add_mutually_exclusive_group()
    replay_modes.add_argument('--capture-replay', metavar='NEW_DIRECTORY',
                              help='make a new four-variant Nebius experiment in a private journal (may call provider)')
    replay_modes.add_argument('--inspect-replay', metavar='JOURNAL_DIRECTORY',
                              help='inspect a local journal offline without printing prompt/response bodies')
    replay_modes.add_argument('--export-replay', metavar='JOURNAL_DIRECTORY',
                              help='export a stored complete bundle to stdout offline (private evidence)')
    replay_modes.add_argument('--replay-bundle', metavar='BUNDLE_JSON',
                              help='recompute observations offline with the exact recorded oracle')
    replay_modes.add_argument('--reevaluate-bundle', metavar='BUNDLE_JSON',
                              help='explicitly recompute observations with the installed oracle')
    replay_modes.add_argument('--replay-repair-evidence', metavar='BUNDLE_JSON',
                              help='reconstruct an L7 decision offline from a captured repair bundle')
    args = parser.parse_args()
    replay_names = ('capture_replay', 'inspect_replay', 'export_replay',
                    'replay_bundle', 'reevaluate_bundle', 'replay_repair_evidence')
    selected = [name for name in replay_names if getattr(args, name) is not None]
    if selected:
        if any(value is not None and value is not False for name, value in vars(args).items()
               if name not in replay_names):
            parser.error('replay modes cannot be combined with other options or a corpus path')
        if selected[0] in ('replay_bundle', 'reevaluate_bundle'):
            from .oracle_replay_cli import run_oracle_replay_command
            return run_oracle_replay_command(selected[0], getattr(args, selected[0]))
        if selected[0] == 'replay_repair_evidence':
            path = Path(getattr(args, selected[0])).expanduser()
            try:
                from .repair_evidence import MAX_EVIDENCE_BYTES
                from .capture_contract import strict_json
                with path.open('rb') as stream:
                    raw_bundle = stream.read(MAX_EVIDENCE_BYTES + 1)
                if len(raw_bundle) > MAX_EVIDENCE_BYTES:
                    raise ValueError('bundle byte limit exceeded')
                bundle = strict_json(raw_bundle.decode('utf-8'))
                from .repair_evidence_replay import replay_repair_evidence
                result = replay_repair_evidence(bundle)
            except (OSError, UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
                result = {
                    'schema_version': 'crucible-repair-evidence-replay/v1',
                    'status': 'INVALID_EVIDENCE',
                    'reason': 'bundle-read-or-shape-failed',
                }
            _emit(result, args.human)
            return 0 if result.get('status') == 'MATCH' else 1
        from .replay_cli import run_replay_command
        return run_replay_command(selected[0], getattr(args, selected[0]))
    if args.include_coverage and not args.scan_installed:
        parser.error('--include-coverage requires --scan-installed')
    if args.scan_installed and args.scan_installed_collection:
        parser.error('--scan-installed and --scan-installed-collection are mutually exclusive')
    if args.scan_root and not (args.scan_installed or args.scan_installed_collection):
        parser.error('--scan-root requires one installed scan mode')
    if args.scan_root and args.root is not None:
        parser.error('--scan-root cannot be combined with a corpus path')
    if args.repair_evidence and not args.repair_loop:
        parser.error('--repair-evidence requires --repair-loop')

    if args.scan_installed_collection:
        from .api import scan_installed_collection
        try:
            result = (scan_installed_collection(roots=args.scan_root)
                      if args.scan_root else scan_installed_collection())
        except (ValueError, OSError) as exc:
            _emit({'status': 'ERROR', 'error': str(exc)}, args.human)
            return 1
        _emit(result, args.human)
        return 0 if result['status'] == 'COMPLETE' else 1

    if args.view:
        with open(args.view, encoding="utf-8") as f:
            artifact = json.load(f)
        print(render_artifact_html(artifact))
        return 0

    if args.serve is not None:
        import uvicorn
        from .api import create_app
        app = create_app()
        host, _, port = args.serve.partition(":")
        port_num = int(port) if port else 8000
        uvicorn.run(app, host=host, port=port_num)
        return 0

    if args.scan_skill:
        import sys
        from .api import scan_skill_text
        skill_text = sys.stdin.read()
        try:
            result = scan_skill_text(skill_text)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        _emit(result["audit"], args.human)
        return 0

    if args.scan_installed:
        import sys
        from .api import scan_installed_skills
        try:
            result = (scan_installed_skills(roots=args.scan_root)
                      if args.scan_root else scan_installed_skills())
        except (ValueError, OSError) as exc:
            _emit({'error': str(exc)}, args.human)
            return 1
        if result.get("error"):
            output = result
            if not args.include_coverage:
                output = {key: value for key, value in result.items() if key != 'coverage'}
            _emit(output, args.human)
            return 1
        coverage = result.get('coverage')
        if coverage and coverage['status'] == 'PARTIAL':
            print(
                f"PARTIAL installed scan: {coverage['analyzed']} analyzed; "
                f"{coverage['skipped']} duplicate packages skipped.",
                file=sys.stderr,
            )
        output = result['audit']
        if args.include_coverage:
            output = {'audit': result['audit'], 'coverage': coverage}
        _emit(output, args.human)
        return 0

    if args.mutate:
        report = run_mutation_lab()
        _emit(report, args.human)
        return 0

    if args.behave:
        if args.local_executor:
            executor = LocalExecutor()
        else:
            executor = NebiusExecutor()
        report = run_behavioral_differential(executor=executor)
        _emit(report, args.human)
        return 0

    if args.bob:
        if args.llm_proposer:
            proposer = LLMProposer()
        else:
            proposer = RuleBasedProposer()
        report = run_bob_workflow(proposer=proposer)
        _emit(report, args.human)
        return 0

    if args.repair_loop:
        if args.repair_evidence:
            if not args.llm_proposer or args.local_executor:
                parser.error("--repair-evidence requires --llm-proposer and cannot use --local-executor")
            bundle = run_captured_repair(args.repair_evidence)
            _emit({
                "evidence_dir": args.repair_evidence,
                "schema_version": bundle["schema_version"],
                "bundle_digest": bundle["bundle_digest"],
                "outcome": bundle["report"].get("outcome"),
                "rejection_reason": bundle["report"].get("rejection_reason"),
                "captured_events": len(bundle["events"]),
            }, args.human)
            return 0
        if args.llm_proposer:
            proposer = LLMProposer()
        else:
            proposer = RuleBasedProposer()
        if args.local_executor:
            executor = LocalExecutor()
        else:
            executor = None  # let the loop decide (Nebius or LocalExecutor fallback)
        report = run_repair_loop(proposer=proposer, executor=executor)
        _emit(report, args.human)
        return 0

    if args.report:
        if args.local_executor:
            executor = LocalExecutor()
        else:
            executor = None  # let the report decide (Nebius or LocalExecutor fallback)
        report = run_full_report(corpus_root=args.root, executor=executor)
        _emit(report, args.human)
        return 0

    if args.confirm:
        if not args.root:
            parser.error("root is required with --confirm")
        artifact = compile_corpus(args.root)
        audit = audit_corpus(artifact)
        if args.mock_confirm:
            executor = MockConfirmExecutor()
        else:
            executor = NebiusConfirmExecutor()
        confirmation = confirm_candidates(audit, artifact, executor)
        _emit(confirmation, args.human)
        return 0

    if args.consolidate or args.consolidate_all:
        if args.consolidate and args.consolidate_all:
            parser.error("--consolidate and --consolidate-all are mutually exclusive")
        if not args.root:
            parser.error("root is required with --consolidate/--consolidate-all")
        artifact = compile_corpus(args.root)
        audit = audit_corpus(artifact)
        root_path = Path(args.root).resolve()
        corpus = {
            skill["identity"]["name"]: (
                root_path / skill["identity"]["source_path"]
            ).read_text(encoding="utf-8")
            for skill in artifact["skills"]
        }
        confirm_executor: Any = (
            MockConfirmExecutor() if args.mock_confirm else NebiusConfirmExecutor()
        )
        confirmation = confirm_candidates(
            audit, artifact, confirm_executor, classes=["SEMANTIC_REDUNDANCY"]
        )
        if args.consolidate_all:
            report = run_consolidation_batch(
                corpus=corpus,
                confirmation=confirmation,
                proposer=LLMConsolidationProposer(),
            )
        else:
            report = run_consolidation(
                corpus=corpus,
                confirmation=confirmation,
                cluster_index=args.cluster_index or 0,
                proposer=LLMConsolidationProposer(),
            )
        _emit(report, args.human)
        return 0

    if args.narrate or args.mock_narrate:
        if not args.root:
            parser.error("root is required with --narrate")
        if args.mock_narrate:
            confirm_executor: Any = MockConfirmExecutor()
            narration_executor: Any = MockNarrationExecutor()
        else:
            confirm_executor = NebiusConfirmExecutor()
            narration_executor = NebiusNarrationExecutor()
        final_report = build_final_report(args.root, confirm_executor, narration_executor)
        _emit(final_report, args.human)
        return 0

    if args.render_report:
        with open(args.render_report, encoding="utf-8") as fh:
            final_report = json.load(fh)
        render_format = args.render_format or "markdown"
        if render_format == "markdown":
            rendered = render_final_report_markdown(final_report)
        elif render_format == "html":
            rendered = render_final_report_html(final_report)
        else:
            rendered = render_final_report_pdf(final_report)
        if isinstance(rendered, bytes):
            if not args.out:
                parser.error("--out is required for --render-format pdf")
            with open(args.out, "wb") as fh:
                fh.write(rendered)
        elif args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(rendered)
        else:
            print(rendered)
        return 0

    if not args.root:
        parser.error("root is required unless --mutate/--behave/--bob/--repair-loop/--report/--view/--render-report is given")

    artifact = compile_corpus(args.root)
    if args.compile_only:
        _emit(artifact, args.human)
        return 0

    audit = audit_corpus(artifact)
    if args.no_graph:
        _emit(audit, args.human)
        return 0

    graph = build_composition_graph(artifact, audit)
    _emit(graph, args.human)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

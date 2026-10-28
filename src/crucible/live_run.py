"""One command for a live narrated-report run that leaves its evidence behind.

    NEBIUS_API_KEY=... python -m crucible.live_run CORPUS --out-dir NEW_DIR

1. Audits the corpus and bounds the model calls (call_estimate.py). If the
   bound exceeds ``--max-calls`` the run stops before calling any model.
2. Builds the report with consolidation and rewrites, counting the calls each
   stage actually makes.
3. Writes report.json (sealed), report.md, report.html, estimate.json and
   RUN.md, a factual summary of the run that needs no editing to be read.

``--mock`` runs the same path with the deterministic stand-ins, for checking
the command before spending calls.
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .bob import LLMProposer, RuleBasedProposer
from .call_estimate import estimate_model_calls
from .compiler import ON_DUPLICATE_ERROR, ON_DUPLICATE_SKIP, compile_corpus
from .confirm import MockConfirmExecutor, NebiusConfirmExecutor
from .consolidation import LLMConsolidationProposer, UnionConsolidationProposer
from .final_report import build_final_report
from .final_report_render import render_final_report_html, render_final_report_markdown
from .narrator import MockNarrationExecutor, NebiusNarrationExecutor


class _Counted:
    """Forward everything to ``inner`` and count the calls that reach a model."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.calls = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def execute(self, *args: Any) -> Any:
        self.calls += 1
        return self._inner.execute(*args)

    def propose(self, *args: Any) -> Any:
        self.calls += 1
        return self._inner.propose(*args)

    def propose_merge(self, *args: Any) -> Any:
        self.calls += 1
        return self._inner.propose_merge(*args)


def _git(args: list[str], cwd: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def _run_md(report: dict[str, Any], estimate: dict[str, Any], actual: dict[str, int],
            meta: dict[str, Any]) -> str:
    skills = report["skills"].values()
    confirmed = sum(len(s["confirmed_finding_ids"]) for s in skills)
    rejected = sum(len(s["rejected_finding_ids"]) for s in skills)
    pending = sum(len(s["pending_finding_ids"]) for s in skills)
    untraceable = sum(len(s["untraceable_finding_ids"]) for s in skills)
    blocked = sum(1 for s in skills if s.get("narration_blocked"))
    errors = sum(1 for s in skills if s.get("narration_error") and not s.get("narration_blocked"))
    summary = report.get("executive_summary") or {}
    corpus = report["corpus"]
    bounds = estimate["max_calls_by_stage"]

    lines = [
        f"# Live narrated report run, {meta['date']}",
        "",
        f"- **Crucible commit:** `{meta['crucible_commit']}`"
        + (" (working tree had uncommitted changes)" if meta["crucible_dirty"] else ""),
        f"- **Corpus:** `{meta['corpus_name']}`"
        + (f" @ `{meta['corpus_commit']}`" if meta["corpus_commit"] else " (not a git checkout)"),
        f"- **Mode:** {'mock stand-ins, no model called' if meta['mock'] else 'live model'}",
        f"- **Model (narration):** `{summary.get('executor_model')}`",
        f"- **Wall time:** {meta['seconds']:.0f} s",
        f"- **Skills:** {report['skill_count']}",
        f"- **Report digest:** `{report['report_digest']}`",
        f"- **Audit digest:** `{report['audit_digest']}`",
        "",
        "## Model calls",
        "",
        "| Stage | Upper bound | Made |",
        "|---|---|---|",
    ]
    for stage in ("confirmation", "narration", "consolidation", "repairs"):
        bound = bounds.get(stage, 0) + (bounds["executive_summary"] if stage == "narration" else 0)
        lines.append(f"| {stage} | {bound} | {actual[stage]} |")
    lines += [
        f"| **total** | {estimate['max_calls_total']} | {sum(actual.values())} |",
        "",
        "## Outcomes",
        "",
        "- **Recommendations:** " + ", ".join(
            f"{k} {v}" for k, v in sorted(report["summary"]["by_recommendation"].items())
        ),
        f"- **Confirmation verdicts on findings:** {confirmed} confirmed, {rejected} rejected, "
        f"{pending} pending (a finding shared by two skills counts once per skill)",
        f"- **Narrations:** {blocked} blocked, {errors} failed, {untraceable} untraceable id(s) cited",
        f"- **Executive summary:** "
        + ("written" if summary.get("narrative") else f"not written ({summary.get('error')})")
        + f", {len(summary.get('untraceable_finding_ids', []))} untraceable id(s)",
        f"- **Duplicate groups:** {len(corpus['consolidation_groups'])}",
        f"- **Contradictions:** {len(corpus['contradictions'])}",
    ]
    proposals = (corpus.get("consolidation") or {}).get("proposals", [])
    if proposals:
        lines += ["", "### Consolidation", "", "| Group | Proposed name | Gate | Reason |", "|---|---|---|---|"]
        for item in proposals:
            lines.append(
                f"| {', '.join(item['members'])} | `{item['proposed_name']}` | {item['outcome']} "
                f"| {item['rejection_reason'] or ''} |"
            )
    rewrites = [(n, s["suggested_rewrite"]) for n, s in sorted(report["skills"].items())
                if s.get("suggested_rewrite")]
    if rewrites:
        lines += ["", "### Rewrites", "", "| Skill | Targeted | Gate | Resolved | Still present | New |",
                  "|---|---|---|---|---|---|"]
        for name, r in rewrites:
            lines.append(
                f"| {name} | {', '.join(r['target_classes'])} | {r['outcome']} "
                f"| {', '.join(r['resolved_classes'])} | {', '.join(r['persisting_classes'])} "
                f"| {', '.join(r['new_findings'])} |"
            )
    lines += [
        "",
        "## What this run does not show",
        "",
        "- That any accepted merge or rewrite changes agent behaviour: both gates re-audit text only.",
        "- That a second run would produce the same prose: the model is not deterministic at temperature 0.",
        "- Anything about corpora other than this one.",
        "",
        "Generated by `python -m crucible.live_run`; the numbers above are read from report.json.",
        "",
    ]
    return "\n".join(lines)


def _stage_slice(corpus: str, names: list[str], on_duplicate: str, into: Path) -> None:
    """Copy only the named skills' SKILL.md files into ``into``."""
    ir = compile_corpus(corpus, on_duplicate_name=on_duplicate)
    by_name = {s["identity"]["name"]: s["identity"]["source_path"] for s in ir["skills"]}
    missing = [n for n in names if n not in by_name]
    if missing:
        raise SystemExit(f"error: not in the corpus: {', '.join(missing)}")
    root = Path(corpus).resolve()
    for name in names:
        (into / name).mkdir()
        shutil.copyfile(root / by_name[name], into / name / "SKILL.md")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m crucible.live_run", description=__doc__.split("\n\n")[0])
    parser.add_argument("corpus", help="directory of skills")
    parser.add_argument("--out-dir", required=True, help="new directory for the run's artifacts")
    parser.add_argument("--max-calls", type=int, default=150,
                        help="stop before calling a model if the estimated bound exceeds this (default 150)")
    parser.add_argument("--repair-limit", type=int, default=5, help="rewrites to attempt (default 5)")
    parser.add_argument("--skip-duplicate-names", action="store_true")
    parser.add_argument("--skills", metavar="NAME,NAME",
                        help="run on these skills only, copied out of the corpus")
    parser.add_argument("--mock", action="store_true", help="deterministic stand-ins, no model")
    args = parser.parse_args(argv)
    if args.skills:
        names = sorted({n.strip() for n in args.skills.split(",") if n.strip()})
        on_duplicate = ON_DUPLICATE_SKIP if args.skip_duplicate_names else ON_DUPLICATE_ERROR
        with tempfile.TemporaryDirectory(prefix="crucible-slice-") as tmpdir:
            _stage_slice(args.corpus, names, on_duplicate, Path(tmpdir))
            return _run(args, tmpdir, parser, slice_of=(args.corpus, names))
    return _run(args, args.corpus, parser, slice_of=None)


def _run(args: Any, corpus: str, parser: Any, slice_of: tuple[str, list[str]] | None) -> int:

    out = Path(args.out_dir)
    if out.exists():
        parser.error(f"{out} already exists; a run never overwrites earlier evidence")
    on_duplicate = ON_DUPLICATE_SKIP if args.skip_duplicate_names else ON_DUPLICATE_ERROR

    estimate = estimate_model_calls(
        corpus, on_duplicate_name=on_duplicate,
        with_consolidation=True, with_repairs=True, repair_limit=args.repair_limit,
    )
    print(f"estimated model calls: at most {estimate['max_calls_total']} "
          f"{estimate['max_calls_by_stage']}", file=sys.stderr)
    if estimate["max_calls_total"] > args.max_calls and not args.mock:
        print(f"stopping: the bound exceeds --max-calls {args.max_calls}; "
              "run on a smaller slice or raise the limit", file=sys.stderr)
        return 2

    if args.mock:
        confirm = _Counted(MockConfirmExecutor())
        narration = _Counted(MockNarrationExecutor())
        merger = _Counted(UnionConsolidationProposer())
        repairer = _Counted(RuleBasedProposer())
    else:
        confirm = _Counted(NebiusConfirmExecutor())
        narration = _Counted(NebiusNarrationExecutor())
        merger = _Counted(LLMConsolidationProposer())
        repairer = _Counted(LLMProposer())
        if not confirm.is_available():
            print("NEBIUS_API_KEY is not set; use --mock to check the command", file=sys.stderr)
            return 2

    start = time.monotonic()
    report = build_final_report(
        corpus, confirm, narration,
        on_duplicate_name=on_duplicate, consolidation_proposer=merger,
        repair_proposer=repairer, repair_limit=args.repair_limit,
        input_scope={"scope": "directory"},
    )
    seconds = time.monotonic() - start

    repo = Path(__file__).resolve().parents[2]
    corpus_path = Path(slice_of[0] if slice_of else corpus).resolve()
    meta = {
        "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "crucible_commit": _git(["rev-parse", "--short=12", "HEAD"], repo),
        "crucible_dirty": bool(_git(["status", "--porcelain"], repo)),
        "corpus_name": corpus_path.name + (
            f" (slice: {', '.join(slice_of[1])})" if slice_of else ""
        ),
        "corpus_commit": _git(["rev-parse", "--short=12", "HEAD"], corpus_path),
        "mock": args.mock,
        "seconds": seconds,
    }
    actual = {
        "confirmation": confirm.calls,
        "narration": narration.calls,
        "consolidation": merger.calls,
        "repairs": repairer.calls,
    }

    out.mkdir(parents=True)
    (out / "estimate.json").write_text(json.dumps(estimate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "report.md").write_text(render_final_report_markdown(report), encoding="utf-8")
    (out / "report.html").write_text(render_final_report_html(report), encoding="utf-8")
    (out / "RUN.md").write_text(_run_md(report, estimate, actual, meta), encoding="utf-8")
    print(f"wrote {out}/RUN.md, report.json, report.md, report.html, estimate.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Measure audit cost against corpus size on deterministic subsamples.

Usage: python measure_scaling.py <corpus-root> <output-dir> [runs]

Subsamples are chosen by sorted relative skill path, so a given corpus and
size always yield the same subsample and its own corpus-provenance record.
Cost values are observations of one machine under one load (see
cost_record.COST_LIMITATION); they are not reproducible and gate nothing.
"""

import json
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'src'))

from crucible.auditor import audit_corpus
from crucible.compiler import compile_corpus
from crucible.cost_record import (
    Stopwatch, build_cost_record, runtime_context, validate_cost_record,
)
from crucible.corpus_provenance import (
    ROLE_TUNING_CONSUMED, build_provenance, validate_provenance,
)
from crucible.graph import build_composition_graph

SIZES = (25, 50, 100, 200, 400, 818)
REPOSITORY = 'https://github.com/mukul975/Anthropic-Cybersecurity-Skills'
CONSUMED_BY = ('docs/evidence/2026-10-02-mukul975-corpus-audit/FINDINGS.md',)


def skill_dirs(root):
    paths = sorted(p.parent for p in Path(root).rglob('SKILL.md'))
    return [p for p in paths if not p.is_symlink()]


def subsample(root, size, destination):
    for source in skill_dirs(root)[:size]:
        shutil.copytree(source, Path(destination) / source.name, symlinks=False)


def measure(root, size, commit, runs):
    with tempfile.TemporaryDirectory() as staging:
        target = root if size is None else staging
        if size is not None:
            subsample(root, size, staging)
        observations = []
        input_bytes = sum(p.stat().st_size for p in Path(target).rglob('SKILL.md'))
        before_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        for _ in range(runs):
            with Stopwatch() as watch:
                ir = compile_corpus(target)
                audit = audit_corpus(ir)
                graph = build_composition_graph(ir, audit)
            after_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            observations.append({
                'wall_ns': watch.wall_ns,
                'peak_rss_kb': max(0, int(after_rss) - int(before_rss)),
            })
        provenance = build_provenance(
            ir, corpus_id=f'mukul975-first-{len(ir["skills"])}-by-path',
            role=ROLE_TUNING_CONSUMED, repository=REPOSITORY, commit=commit,
            consumed_by=CONSUMED_BY,
        )
        validate_provenance(provenance)
        record = build_cost_record(
            corpus_id=provenance['corpus_id'],
            corpus_provenance_digest=provenance['provenance_digest'],
            audit_digest=audit['audit_digest'],
            scale={
                'skill_count': len(ir['skills']),
                'input_bytes': input_bytes,
                'finding_count': audit['summary']['total'],
                'edge_count': len(graph['edges']),
            },
            runs=observations,
            context=runtime_context(),
        )
        validate_cost_record(record)
        return record


def main():
    root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    runs = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    commit = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, check=True).stdout.strip()
    if subprocess.run(['git', '-C', str(root), 'status', '--porcelain'],
                      capture_output=True, text=True, check=True).stdout:
        raise SystemExit('corpus worktree is not clean; refusing to measure')
    out.mkdir(parents=True, exist_ok=True)
    total = len(skill_dirs(root))
    series = []
    for size in SIZES:
        record = measure(root, None if size >= total else size, commit, runs)
        series.append(record)
        scale, extent = record['scale'], record['range']
        print(f"{scale['skill_count']:>5} skills  "
              f"{extent['wall_ns']['min'] // 1_000_000:>6} ms  "
              f"{scale['finding_count']:>5} findings  "
              f"{scale['edge_count']:>4} edges")
    with (out / 'cost-series.json').open('w') as fh:
        json.dump({'schema_version': 'cost-series/v1', 'runs_per_size': runs,
                   'records': series}, fh, indent=1, sort_keys=True)
        fh.write('\n')


if __name__ == '__main__':
    main()

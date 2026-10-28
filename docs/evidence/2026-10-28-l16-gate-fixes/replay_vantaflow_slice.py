"""Replay the 2026-10-24 refused L16 merge on the real vantaflow skills.

No model is called. The merge is a deterministic stand-in for the lost
Nemotron proposal: the first member's text renamed to the name the model
chose (structured-bug-debugger), followed by the other members' bodies, so
that coverage passes and only the novelty and redundancy gates decide.

Usage:
    git clone https://github.com/vantaflow/claude-skills-collection vantaflow
    git -C vantaflow checkout f88a34d0f75e
    python docs/evidence/2026-10-28-l16-gate-fixes/replay_vantaflow_slice.py vantaflow
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from crucible.consolidation import _compile_ir_and_audit, run_consolidation

SLICE = {
    "bug-debugger": "dev-skills/bug-debugger",
    "dev-bug-debugger": "skills/dev-bug-debugger",
    "debugger": "prompt-skills/debugger",
    "prompt-debugger": "skills/prompt-debugger",
}


class UnionProposer:
    def propose_merge(self, cluster_skills, evidence, context):
        text = re.sub(r"(?m)^name:.*$", "name: structured-bug-debugger",
                      cluster_skills[0]["text"], count=1)
        for other in cluster_skills[1:]:
            text += "\n" + other["text"].split("---", 2)[2]
        return {"proposed_name": "structured-bug-debugger", "proposed_text": text,
                "rationale": "deterministic replay", "proposer": "replay"}


def main(root: Path) -> None:
    corpus = {name: (root / rel / "SKILL.md").read_text(encoding="utf-8")
              for name, rel in SLICE.items()}
    _, audit = _compile_ir_and_audit(corpus)
    confirmation = {"confirmations": [
        {"finding_id": f["id"], "verdict": "CONFIRMED"}
        for f in audit["findings"] if f["class"] == "SEMANTIC_REDUNDANCY"
    ]}
    for index in (0, 1):
        report = run_consolidation(corpus=corpus, confirmation=confirmation,
                                   cluster_index=index, proposer=UnionProposer())
        print(index, report["cluster"], report["outcome"],
              report["rejection_reason"], report["new_findings"],
              report["redundancy_resolved"])


if __name__ == "__main__":
    main(Path(sys.argv[1]))

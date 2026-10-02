"""L15 LLM narrator.

Turns one skill's deterministic L15 recommendation (recommendation.py) and
its underlying L2 findings into prose, using an LLM. The LLM chooses only
wording and the ordering of improvement suggestions. It never chooses the
recommendation bucket (KEEP / MODIFY / DELETE / NEEDS_CONFIRMATION) --
that is computed deterministically beforehand and handed to the model as a
fixed fact it is instructed not to contradict.

Traceability: ``extract_cited_finding_ids`` scans the model's narrative for
finding-id-shaped tokens, and ``check_traceability`` confirms every cited
id is one this skill's recommendation actually carries. An id the model
invents that does not exist in the sealed artifacts is reported as an
untraceable claim, not silently shown as if it were evidence -- the same
discipline ZAYNOR/VIGIA apply to their own narration layers.

A skill with recommendation KEEP is never sent to the model: there is
nothing to narrate, and a model asked to narrate "no findings" has an
unnecessary opportunity to invent concerns that were never raised.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Protocol

from .ir import digest_payload

NARRATION_VERSION = "crucible-narration/v1"
NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
NEBIUS_DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"

_FINDING_ID_PATTERN = re.compile(r"\bfinding-\d{4}\b")

# A model may render the ASCII hyphen-minus (U+002D) in "finding-NNNN" as a
# visually similar Unicode dash instead -- observed live from Nemotron as
# U+2011 (NON-BREAKING HYPHEN). Normalize every dash-like codepoint to
# U+002D before matching, so citation extraction does not silently miss ids
# the model actually discussed just because of which dash it rendered.
_DASH_VARIANTS = "‐‑‒–—―−"
_DASH_NORMALIZE_TABLE = str.maketrans({ch: "-" for ch in _DASH_VARIANTS})


def _normalize_dashes(text: str) -> str:
    return text.translate(_DASH_NORMALIZE_TABLE)


class NarrationExecutor(Protocol):
    def execute(self, system_prompt: str, user_prompt: str) -> dict[str, Any]: ...


class NebiusNarrationExecutor:
    """Calls Nebius Token Factory. Mirrors confirm.NebiusConfirmExecutor's
    HTTP mechanics; kept as its own class per this codebase's existing
    per-level executor convention (behavioral/confirm each have their own
    rather than sharing one)."""

    def __init__(
        self,
        model: str = NEBIUS_DEFAULT_MODEL,
        temperature: int = 0,
        max_tokens: int = 1500,
        api_key: str | None = None,
        base_url: str = NEBIUS_BASE_URL,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key or os.environ.get("NEBIUS_API_KEY")
        self.base_url = base_url

    def is_available(self) -> bool:
        return bool(self.api_key)

    def execute(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key:
            return {
                "output": "",
                "error": "NEBIUS_API_KEY not set; cannot call Nebius",
                "model": self.model,
                "provider": "nebius-token-factory",
                "blocked": True,
            }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + "chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "*/*",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    result = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                return {
                    "output": "",
                    "error": f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:200]}",
                    "model": self.model,
                    "provider": "nebius-token-factory",
                    "blocked": False,
                }
            except urllib.error.URLError as exc:
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                return {
                    "output": "",
                    "error": f"URL error: {exc}",
                    "model": self.model,
                    "provider": "nebius-token-factory",
                    "blocked": False,
                }
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            return {
                "output": "",
                "error": "provider response has no choices",
                "model": self.model,
                "provider": "nebius-token-factory",
                "blocked": False,
                "finish_reason": None,
                "truncated": False,
            }
        choice = choices[0]
        message = choice.get("message", {})
        output = message.get("content") if isinstance(message, dict) else None
        finish_reason = choice.get("finish_reason")
        usage = result.get("usage", {})
        response = {
            "output": output if isinstance(output, str) else "",
            "error": None if isinstance(output, str) else f"provider returned non-text content: {type(output).__name__}",
            "model": self.model,
            "provider": "nebius-token-factory",
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            "response_id": result.get("id", ""),
            "blocked": False,
            "finish_reason": finish_reason,
            "truncated": finish_reason == "length",
        }
        return response


class MockNarrationExecutor:
    """Deterministic executor for testing without NEBIUS_API_KEY. Produces
    a fixed-shape narrative that cites exactly the finding ids it is given,
    so traceability tests can exercise both the pass and fail paths by
    controlling the input rather than the mock."""

    def __init__(self) -> None:
        self.model = "crucible-mock-narration/v1"

    def execute(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        cited = _FINDING_ID_PATTERN.findall(user_prompt)
        body = " ".join(f"See {fid}." for fid in dict.fromkeys(cited))
        return {
            "output": f"Mock narration. {body}".strip(),
            "error": None,
            "model": self.model,
            "provider": "crucible-mock",
            "blocked": False,
            "finish_reason": "stop",
            "truncated": False,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "response_id": "mock",
        }


_SYSTEM_PROMPT = (
    "You write a short engineering narrative for a skill-quality audit. "
    "You are given a recommendation that has ALREADY been decided by a "
    "deterministic engine; you must not propose a different recommendation "
    "than the one stated, and you must not invent findings that are not "
    "listed below. Cite every finding you discuss by its exact finding-NNNN "
    "id. Be concise and concrete. Do not use markdown headings."
)


def _build_user_prompt(
    skill_name: str,
    recommendation: str,
    cited_findings: list[dict[str, Any]],
) -> str:
    lines = [
        f"Skill: {skill_name}",
        f"Decided recommendation (do not contradict this): {recommendation}",
        "",
        "Findings (cite only these ids):",
    ]
    for finding in cited_findings:
        lines.append(
            f"- {finding.get('id')}: class={finding.get('class')} "
            f"status={finding.get('status', 'unknown')} "
            f"evidence={finding.get('evidence', '')!r} "
            f"violated_invariant={finding.get('violated_invariant') or 'none stated'}"
        )
    lines += [
        "",
        "Write: (1) one short paragraph explaining why this recommendation "
        "follows from the findings above, citing their ids; (2) if the "
        "recommendation is MODIFY or DELETE, a short prioritized list of "
        "concrete next steps.",
    ]
    return "\n".join(lines)


def extract_cited_finding_ids(text: str) -> list[str]:
    return sorted(set(_FINDING_ID_PATTERN.findall(_normalize_dashes(text or ""))))


def check_traceability(
    cited_ids: list[str], known_ids: set[str]
) -> list[str]:
    """Return cited ids that are NOT among the ids this skill's sealed
    recommendation actually carries -- an untraceable claim."""
    return sorted(set(cited_ids) - known_ids)


def narrate_skill(
    skill_name: str,
    skill_recommendation: dict[str, Any],
    findings_by_id: dict[str, dict[str, Any]],
    executor: NarrationExecutor,
) -> dict[str, Any]:
    """Narrate one skill's already-decided recommendation.

    ``skill_recommendation`` is the per-skill entry from
    ``recommendation.compute_recommendations(...)["skills"][skill_name]``.
    ``findings_by_id`` maps every finding id in the source audit to its
    full finding dict, used to build the prompt and to label each cited
    finding's resolution status (confirmed/rejected/pending) for the model.
    """
    recommendation = skill_recommendation["recommendation"]
    known_ids = set(skill_recommendation["confirmed_finding_ids"]) | set(
        skill_recommendation["pending_finding_ids"]
    )

    result: dict[str, Any] = {
        "schema_version": NARRATION_VERSION,
        "skill": skill_name,
        "recommendation": recommendation,
        "narrative": None,
        "cited_finding_ids": [],
        "untraceable_finding_ids": [],
        "blocked": False,
        "error": None,
    }

    if recommendation == "KEEP":
        result["narrative"] = "No findings for this skill; no action recommended."
        result["narration_digest"] = digest_payload(result)
        return result

    status_by_id = {fid: "confirmed" for fid in skill_recommendation["confirmed_finding_ids"]}
    status_by_id.update({fid: "pending confirmation" for fid in skill_recommendation["pending_finding_ids"]})

    cited_findings = []
    for fid in sorted(known_ids):
        finding = dict(findings_by_id.get(fid, {"id": fid}))
        finding["status"] = status_by_id.get(fid, "unknown")
        cited_findings.append(finding)

    system_prompt = _SYSTEM_PROMPT
    user_prompt = _build_user_prompt(skill_name, recommendation, cited_findings)
    response = executor.execute(system_prompt, user_prompt)

    result["executor_model"] = response.get("model")
    result["executor_provider"] = response.get("provider")
    result["runtime"] = {
        "response_id": response.get("response_id"),
        "finish_reason": response.get("finish_reason"),
        "usage": response.get("usage"),
    }

    if response.get("blocked"):
        result["blocked"] = True
        result["error"] = response.get("error")
        result["narration_digest"] = digest_payload(result)
        return result
    if response.get("error") or not response.get("output"):
        result["error"] = response.get("error") or "empty provider response"
        result["narration_digest"] = digest_payload(result)
        return result

    narrative = response["output"]
    cited_ids = extract_cited_finding_ids(narrative)
    untraceable = check_traceability(cited_ids, known_ids)

    result["narrative"] = narrative
    result["cited_finding_ids"] = cited_ids
    result["untraceable_finding_ids"] = untraceable
    result["narration_digest"] = digest_payload(result)
    return result

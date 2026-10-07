"""Behavioral differential harness (L5).

Runs the same task against four skill variants (no-skill, original, mutant,
repair) and observes whether the model's behavior satisfies explicit
properties. The property oracle is deterministic; the model is the subject of
observation, not the judge.

Architecture:

    task fixture + skill variant
            |
            v
        executor (Nemotron via Nebius, or local deterministic)
            |
            v
        model output
            |
            v
        property oracle (deterministic checks)
            |
            v
        sealed observation report

The executor is pluggable. The Nebius executor calls the Token Factory API
with a pinned NVIDIA Nemotron model. The local executor is a deterministic
responder for testing the harness without external dependencies.

If the Nebius API key is not available, the Nebius execution is documented
as BLOCKED, not simulated as verified.

Each property observation carries a structured activation trace in its
``evidence`` field (which keyword was searched, which one matched the
real output, and a readable snippet) instead of a static description
restated as a sentence. This is a deterministic, falsifiable, LEXICAL
trace of how the model's output relates to each property -- it is not a
claim about the model's internal reasoning, attention, or whether it
"used" the skill text in any mechanistic sense; a model could produce a
matching keyword by coincidence, or phrase an equivalent idea without
using any searched keyword (an ABSTAINED-worthy gap this oracle cannot
distinguish from genuine absence). It is bounded, honest observability,
not a causal activation proof.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Callable, Protocol

from .ir import digest_payload

BEHAVIORAL_VERSION = "crucible-behavioral/v1"

# ---------------------------------------------------------------------------
# Task fixture
# ---------------------------------------------------------------------------

# The task is a user prompt that an agent would execute. It is the same for
# all four variants. The skill variant provides the system prompt (guidance).
TASK_FIXTURE: dict[str, Any] = {
    "task_id": "retry-strategy-design",
    "task_prompt": (
        "Apply the supplied methodology exactly when answering; do not "
        "replace it with your default best practices. "
        "Design a retry strategy for a payment processing system. "
        "Describe the retry budget, when to retry, and any exceptions."
    ),
    "task_digest": "",  # filled below
    "properties": [
        {
            "property_id": "P1-mentions-budget",
            "description": "The response mentions a finite or bounded retry budget.",
            "check": "mentions_budget",
        },
        {
            "property_id": "P2-respects-exception",
            "description": "The response acknowledges that some operations may be exempt from the budget.",
            "check": "respects_exception",
        },
        {
            "property_id": "P3-no-unbounded-retry",
            "description": "The response does not recommend retrying without any bound.",
            "check": "no_unbounded_retry",
        },
        {
            "property_id": "P4-mentions-idempotency",
            "description": "The response mentions idempotency or idempotent operations.",
            "check": "mentions_idempotency",
        },
    ],
}

# Seal the task fixture digest.
_task_canonical = json.dumps(
    {"task_id": TASK_FIXTURE["task_id"], "task_prompt": TASK_FIXTURE["task_prompt"]},
    ensure_ascii=False,
    sort_keys=True,
)
TASK_FIXTURE["task_digest"] = "sha256:" + hashlib.sha256(
    _task_canonical.encode("utf-8")
).hexdigest()

# ---------------------------------------------------------------------------
# Skill variants
# ---------------------------------------------------------------------------

# The four variants use the L4 base fixture and its mutations.
# Each variant provides a system prompt derived from the skill text.

VARIANT_NO_SKILL = {
    "variant_id": "V1-no-skill",
    "description": "No skill guidance; the agent runs without methodology constraints.",
    "skill_text": "",
}

VARIANT_ORIGINAL = {
    "variant_id": "V2-original",
    "description": "Original skill with bounded retries and exception clause.",
    "skill_text": (
        "You are guided by the retrier skill. "
        "Retries MUST have a finite budget, except for read-only operations. "
        "The operation SHOULD be idempotent before retrying."
    ),
}

VARIANT_MUTANT = {
    "variant_id": "V3-mutant-polarity-inversion",
    "description": "Mutated skill with polarity inversion: MUST NOT have a finite budget.",
    "skill_text": (
        "You are guided by the retrier skill. "
        "Retries MUST NOT have a finite budget. "
        "The operation SHOULD be idempotent before retrying."
    ),
}

VARIANT_REPAIR = {
    "variant_id": "V4-repair",
    "description": "Repaired skill: restores the finite budget with a specific number.",
    "skill_text": (
        "You are guided by the retrier skill. "
        "Retries MUST have a finite budget of at most 5 attempts, "
        "except for read-only operations. "
        "The operation SHOULD be idempotent before retrying."
    ),
}

ALL_VARIANTS = [
    VARIANT_NO_SKILL,
    VARIANT_ORIGINAL,
    VARIANT_MUTANT,
    VARIANT_REPAIR,
]

# ---------------------------------------------------------------------------
# Executor protocol
# ---------------------------------------------------------------------------

class Executor(Protocol):
    """Pluggable executor interface for model inference."""

    def execute(
        self, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        """Run the model and return a response dict with output and metadata."""
        ...


# ---------------------------------------------------------------------------
# Nebius Token Factory executor (NVIDIA Nemotron)
# ---------------------------------------------------------------------------

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
NEBIUS_DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"
NEBIUS_DEFAULT_TEMPERATURE = 0
NEBIUS_DEFAULT_MAX_TOKENS = 4000


class NebiusExecutor:
    """Executor that calls the Nebius Token Factory API with NVIDIA Nemotron.

    Requires NEBIUS_API_KEY in the environment. If the key is not present,
    ``execute`` raises ``MissingCredentialError`` so the harness can mark
    the run as BLOCKED rather than simulating it.
    """

    def __init__(
        self,
        model: str = NEBIUS_DEFAULT_MODEL,
        temperature: int = NEBIUS_DEFAULT_TEMPERATURE,
        max_tokens: int = NEBIUS_DEFAULT_MAX_TOKENS,
        api_key: str | None = None,
        base_url: str = NEBIUS_BASE_URL,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key or os.environ.get("NEBIUS_API_KEY")
        self.base_url = base_url

    def is_available(self) -> bool:
        """Check whether the API key is present."""
        return bool(self.api_key)

    def execute(
        self, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        if not self.api_key:
            raise MissingCredentialError(
                "NEBIUS_API_KEY is not set; cannot call Nebius Token Factory"
            )
        request = self._prepare_request(system_prompt, user_prompt)
        return self._execute_request(request)

    def capture_exchange(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Make one bounded transport capture, not a behavioral/replay verdict.

        This is an explicit alternative to execute, not a second call after it.
        Capture content may contain private prompts and provider-echoed secrets.
        """
        from .runtime_capture import capture_exchange

        if type(system_prompt) is not str or type(user_prompt) is not str:
            raise ValueError('capture prompts must be strings')
        request = self._prepare_request(system_prompt, user_prompt)
        return capture_exchange(
            request, system_prompt=system_prompt, user_prompt=user_prompt,
            available=self.is_available(), open_request=urllib.request.urlopen,
        )

    def _prepare_request(self, system_prompt: str, user_prompt: str) -> urllib.request.Request:
        """Shared wire payload; capture must observe the same prompt fallback."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return urllib.request.Request(
            self.base_url + "chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "*/*",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

    def _execute_request(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return {
                "output": "",
                "error": f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:200]}",
                "model": self.model,
                "provider": "nebius-token-factory",
            }
        except urllib.error.URLError as exc:
            return {
                "output": "",
                "error": f"URL error: {exc}",
                "model": self.model,
                "provider": "nebius-token-factory",
            }
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {
                "output": "",
                "error": "invalid provider response: body is not UTF-8 JSON",
                "model": self.model,
                "provider": "nebius-token-factory",
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "usage": {},
                "response_id": "",
                "finish_reason": None,
                "truncated": False,
            }

        def invalid_response(reason: str) -> dict[str, Any]:
            return {
                "output": "",
                "error": f"invalid provider response: {reason}",
                "model": self.model,
                "provider": "nebius-token-factory",
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "usage": {},
                "response_id": result.get("id", "") if isinstance(result, dict) else "",
                "finish_reason": None,
                "truncated": False,
            }

        if not isinstance(result, dict):
            return invalid_response("root must be an object")
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            return {
                "output": "",
                "error": "provider response has no choices",
                "model": self.model,
                "provider": "nebius-token-factory",
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "usage": {},
                "response_id": result.get("id", ""),
                "finish_reason": None,
                "truncated": False,
            }
        choice = choices[0]
        if not isinstance(choice, dict):
            return invalid_response("choices[0] must be an object")
        message = choice.get("message")
        if not isinstance(message, dict):
            return invalid_response("choices[0].message must be an object")
        output = message.get("content")
        finish_reason = choice.get("finish_reason")
        usage = result.get("usage", {})
        if not isinstance(usage, dict):
            return invalid_response("usage must be an object")
        token_counts = {
            key: usage.get(key, 0)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        }
        if any(type(value) is not int or value < 0 for value in token_counts.values()):
            return invalid_response("usage token counts must be non-negative integers")
        if finish_reason is not None and not isinstance(finish_reason, str):
            return invalid_response("choices[0].finish_reason must be a string or null")
        response_id = result.get("id")
        usage_complete = (
            isinstance(usage, dict)
            and all(key in usage for key in token_counts)
            and all(type(usage[key]) is int and usage[key] >= 0 for key in token_counts)
            and usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
        )
        runtime_metadata_complete = (
            isinstance(response_id, str) and bool(response_id)
            and finish_reason == "stop"
            and usage_complete
            and isinstance(output, str) and bool(output.strip())
        )
        response = {
            "output": output,
            "error": None,
            "model": self.model,
            "provider": "nebius-token-factory",
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "usage": token_counts,
            "response_id": response_id if isinstance(response_id, str) else "",
            "finish_reason": finish_reason,
            "truncated": finish_reason == "length",
            "runtime_metadata_complete": runtime_metadata_complete,
        }
        if not isinstance(output, str):
            response["output"] = ""
            response["error"] = (
                "provider returned non-text content: "
                f"{type(output).__name__}"
            )
        return response


class MissingCredentialError(Exception):
    """Raised when a required API credential is not available."""


# ---------------------------------------------------------------------------
# Local deterministic executor (for testing without external dependencies)
# ---------------------------------------------------------------------------

class LocalExecutor:
    """Deterministic executor for testing the harness.

    Generates a response based on the skill text using pattern matching.
    The response is deterministic: the same inputs always produce the same
    output. No LLM, no network, no randomness.
    """

    def __init__(self) -> None:
        self.model = "crucible-local-deterministic/v1"
        self.temperature = 0
        self.max_tokens = 0

    def execute(
        self, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        skill = system_prompt.lower()
        output_parts = []

        # Simulate model behavior based on skill guidance.
        if "must not have a finite budget" in skill:
            # Polarity inversion: the model follows the inverted rule.
            output_parts.append(
                "Retry strategy: retries should not be bounded by a finite budget. "
                "Continue retrying until the operation succeeds."
            )
        elif "finite budget of at most 5" in skill:
            # Repair variant: specific budget.
            output_parts.append(
                "Retry strategy: use a finite budget of at most 5 retry attempts."
            )
        elif "must have a finite budget" in skill:
            # Original skill: mentions budget.
            output_parts.append(
                "Retry strategy: use a finite retry budget to bound the number of attempts."
            )
        else:
            # No skill guidance.
            output_parts.append(
                "Retry strategy: retry failed operations until they succeed."
            )

        # Exception clause.
        if "except for read-only operations" in skill:
            output_parts.append(
                "Exception: read-only operations may be retried without the budget."
            )

        # Idempotency.
        if "idempotent" in skill:
            output_parts.append(
                "Ensure the operation is idempotent before retrying."
            )

        output = " ".join(output_parts)
        output_hash = hashlib.sha256(output.encode("utf-8")).hexdigest()
        return {
            "output": output,
            "error": None,
            "model": self.model,
            "provider": "local-deterministic",
            "temperature": 0,
            "max_tokens": 0,
            "usage": {
                "prompt_tokens": len(system_prompt) + len(user_prompt),
                "completion_tokens": len(output),
                "total_tokens": len(system_prompt) + len(user_prompt) + len(output),
            },
            "response_id": f"local-{output_hash[:16]}",
        }


# ---------------------------------------------------------------------------
# Property oracle (deterministic)
# ---------------------------------------------------------------------------

def _snippet(output_original: str, start: int, length: int, window: int = 30) -> str:
    """A short window of the model's ORIGINAL-case output around a match
    position, for a human-readable trace. _normalize_oracle_text only
    lowercases and 1:1-substitutes dash variants, so a position found in
    the normalized text maps directly to the same index in the original
    -- the caller passes the pre-normalization output here so the quoted
    snippet reads naturally instead of all-lowercase."""
    lo = max(0, start - window)
    hi = min(len(output_original), start + length + window)
    prefix = "..." if lo > 0 else ""
    suffix = "..." if hi < len(output_original) else ""
    return prefix + output_original[lo:hi].strip() + suffix


def _has_negation(output_lower: str, keyword: str) -> bool:
    """Check whether a keyword is negated in the output.

    Looks for negation words within a small window before OR after the
    keyword. "budget is not needed" fails because "not" follows "budget".
    """
    negation_words = ("not ", "no ", "without ", "never ", "isn't ", "aren't ")
    pos = output_lower.find(keyword)
    while pos != -1:
        # Check the 30 characters before the keyword for a negation word.
        before_start = max(0, pos - 30)
        before_window = output_lower[before_start:pos]
        # Check the 30 characters after the keyword for a negation word.
        after_window = output_lower[pos + len(keyword):pos + len(keyword) + 30]
        if any(neg in before_window for neg in negation_words):
            return True
        if any(neg in after_window for neg in negation_words):
            return True
        pos = output_lower.find(keyword, pos + 1)
    return False


def _check_mentions_budget(output: str) -> tuple[str, dict[str, Any]]:
    """P1: The response mentions a finite or bounded retry budget.

    Checks for keyword presence with negation detection: "budget is not
    needed" fails because the keyword is negated.
    """
    output_lower = _normalize_oracle_text(output)
    keywords = ("finite", "bounded", "budget", "at most")
    for kw in keywords:
        pos = output_lower.find(kw)
        if pos != -1 and not _has_negation(output_lower, kw):
            return "PASS", {
                "basis": "keyword_present", "matched_keyword": kw,
                "snippet": _snippet(output, pos, len(kw)),
                "keywords_checked": list(keywords),
            }
    return "FAIL", {
        "basis": "no_keyword_or_all_negated", "matched_keyword": None,
        "snippet": None, "keywords_checked": list(keywords),
    }


def _check_respects_exception(output: str) -> tuple[str, dict[str, Any]]:
    """P2: The response acknowledges that some operations may be exempt.

    Checks for keyword presence with negation detection: "there is no
    exception" fails because the keyword is negated.
    """
    output_lower = _normalize_oracle_text(output)
    explicit_denials = (
        "no exception",
        "no exceptions",
        "without exception",
        "without exceptions",
        "exceptions are not allowed",
        "exceptions are not permitted",
    )
    for denial in explicit_denials:
        pos = output_lower.find(denial)
        if pos != -1:
            return "FAIL", {
                "basis": "explicit_denial", "matched_keyword": denial,
                "snippet": _snippet(output, pos, len(denial)),
                "keywords_checked": list(explicit_denials),
            }
    keywords = ("except", "exempt", "exception", "read-only")
    for kw in keywords:
        pos = output_lower.find(kw)
        if pos != -1:
            return "PASS", {
                "basis": "keyword_present", "matched_keyword": kw,
                "snippet": _snippet(output, pos, len(kw)),
                "keywords_checked": list(keywords),
            }
    return "FAIL", {
        "basis": "no_keyword_found", "matched_keyword": None,
        "snippet": None, "keywords_checked": list(keywords),
    }


def _check_no_unbounded_retry(output: str) -> tuple[str, dict[str, Any]]:
    """P3: The response does not recommend retrying without any bound.

    A negation pattern ("not be bounded", "no finite budget") fails
    unconditionally: a positive bound appearing elsewhere does not rescue
    an explicit unbounded recommendation. The positive bound only rescues
    the weaker "until the operation succeeds" pattern, where the bound
    may be the primary recommendation and "until succeeds" a fallback.
    """
    output_lower = _normalize_oracle_text(output)
    # Negation patterns that recommend unbounded retry.
    negation_patterns = [
        "not be bounded",
        "no finite budget",
        "without any bound",
        "unbounded",
        "not bounded by",
    ]
    # If any negation pattern is present, FAIL unconditionally.
    for pattern in negation_patterns:
        pos = output_lower.find(pattern)
        if pos != -1:
            return "FAIL", {
                "basis": "unbounded_pattern", "matched_keyword": pattern,
                "snippet": _snippet(output, pos, len(pattern)),
                "keywords_checked": negation_patterns,
            }
    # "Continue retrying until" is an unbounded recommendation.
    unbounded_recommendation_pos = output_lower.find("until the operation succeeds")
    has_unbounded_recommendation = unbounded_recommendation_pos != -1
    # Positive bound: "budget of N" or "at most N" that is NOT negated.
    has_positive_bound = False
    bound_match = None
    for match in re.finditer(
        r"(?:budget of|at most|finite budget of)\s+\d+",
        output_lower,
    ):
        window_start = max(0, match.start() - 30)
        window = output_lower[window_start:match.start()]
        if not any(neg in window for neg in ("not ", "no ", "without ", "never ")):
            has_positive_bound = True
            bound_match = match
            break
    if has_unbounded_recommendation and not has_positive_bound:
        return "FAIL", {
            "basis": "unbounded_recommendation_without_positive_bound",
            "matched_keyword": "until the operation succeeds",
            "snippet": _snippet(
                output, unbounded_recommendation_pos,
                len("until the operation succeeds"),
            ),
            "keywords_checked": negation_patterns + ["until the operation succeeds"],
        }
    if has_positive_bound:
        return "PASS", {
            "basis": "positive_bound_present", "matched_keyword": bound_match.group(),
            "snippet": _snippet(output, bound_match.start(), len(bound_match.group())),
            "keywords_checked": negation_patterns,
        }
    return "PASS", {
        "basis": "no_unbounded_pattern_found", "matched_keyword": None,
        "snippet": None, "keywords_checked": negation_patterns,
    }


def _check_mentions_idempotency(output: str) -> tuple[str, dict[str, Any]]:
    """P4: The response mentions idempotency or idempotent operations."""
    output_lower = _normalize_oracle_text(output)
    for kw in ("idempotent", "idempotency"):
        pos = output_lower.find(kw)
        if pos != -1:
            return "PASS", {
                "basis": "keyword_present", "matched_keyword": kw,
                "snippet": _snippet(output, pos, len(kw)),
                "keywords_checked": ["idempotent", "idempotency"],
            }
    return "FAIL", {
        "basis": "no_keyword_found", "matched_keyword": None,
        "snippet": None, "keywords_checked": ["idempotent", "idempotency"],
    }


def _normalize_oracle_text(output: str) -> str:
    """Normalize provider typography before deterministic lexical checks."""
    return output.lower().translate(str.maketrans({
        "‐": "-",  # hyphen
        "‑": "-",  # non-breaking hyphen
        "‒": "-",  # figure dash
        "–": "-",  # en dash
        "—": "-",  # em dash
        "−": "-",  # minus sign
    }))


PROPERTY_CHECKS: dict[str, Callable[[str], tuple[str, dict[str, Any]]]] = {
    "mentions_budget": _check_mentions_budget,
    "respects_exception": _check_respects_exception,
    "no_unbounded_retry": _check_no_unbounded_retry,
    "mentions_idempotency": _check_mentions_idempotency,
}


def _format_evidence(trace: dict[str, Any]) -> str:
    """Render a check function's trace dict as the sealed ``evidence``
    string.

    ``evidence`` stays plain text -- replay.py's capture-bundle validator
    (crucible-capture-bundle/v1, R2/R3) requires each observation to have
    EXACTLY the fields {property_id, status, evidence} and requires
    evidence to be ``str`` (``_fields``/``_text`` in replay.py). That is a
    deliberately closed, sealed contract for tamper-evident replay, not an
    incidental shape to relax for a new field; the richer trace (matched
    keyword, snippet, keywords checked) is folded into this one string
    instead of added as a new dict/field.
    """
    if trace["matched_keyword"] is None:
        checked = ", ".join(repr(k) for k in trace["keywords_checked"])
        return f"{trace['basis']}: none of [{checked}] found in output"
    return (
        f"{trace['basis']}: matched {trace['matched_keyword']!r} "
        f"in \"{trace['snippet']}\""
    )


def run_property_oracle(
    output: str, properties: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Run deterministic property checks against the model output.

    ``evidence`` is now a genuine activation trace rendered as text --
    which keywords were searched, which one (if any) actually matched in
    the model's real output, and a readable snippet around that match --
    instead of a static sentence restating the property description
    regardless of outcome. This is the deterministic, falsifiable answer
    to "how did the model's output relate to this property": a lexical
    trace, not a claim about the model's internal reasoning or attention
    (see the module docstring's limitations).
    """
    observations = []
    for prop in properties:
        check_fn = PROPERTY_CHECKS.get(prop["check"])
        if check_fn is None:
            status = "ABSTAINED"
            trace: dict[str, Any] = {
                "basis": "check_not_found", "matched_keyword": None,
                "snippet": None, "keywords_checked": [],
            }
        else:
            status, trace = check_fn(output)
        observations.append({
            "property_id": prop["property_id"],
            "description": prop["description"],
            "status": status,
            "evidence": _format_evidence(trace),
        })
    return observations


# ---------------------------------------------------------------------------
# Behavioral differential runner
# ---------------------------------------------------------------------------

def run_behavioral_differential(
    executor: Executor | None = None,
    task: dict[str, Any] | None = None,
    variants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the behavioral differential harness.

    If no executor is given, uses NebiusExecutor. If the Nebius API key is
    not available, the run is marked BLOCKED and a LocalExecutor run is
    provided as a fallback for harness verification.
    """
    if task is None:
        task = TASK_FIXTURE
    if variants is None:
        variants = ALL_VARIANTS

    if executor is None:
        executor = NebiusExecutor()

    runs = []
    blocked = False
    block_reason = None

    for variant in variants:
        run = _run_variant(executor, variant, task)
        if run["status"] == "BLOCKED":
            blocked = True
            block_reason = run.get("error", "executor unavailable")
        runs.append(run)

    # If Nebius is blocked, also run with LocalExecutor for harness verification.
    local_runs = None
    if blocked:
        local_executor = LocalExecutor()
        local_runs = []
        for variant in variants:
            local_runs.append(_run_variant(local_executor, variant, task))

    report: dict[str, Any] = {
        "behavioral_version": BEHAVIORAL_VERSION,
        "task_id": task["task_id"],
        "task_digest": task["task_digest"],
        "executor": _executor_metadata(executor),
        "runs": runs,
        "local_fallback_runs": local_runs,
        "nebius_blocked": blocked,
        "block_reason": block_reason if blocked else None,
        "differential_summary": _summarize_differential(runs, local_runs),
        "limitations": BEHAVIORAL_LIMITATIONS,
    }
    report["behavioral_digest"] = digest_payload(report)
    return report


def _run_variant(
    executor: Executor, variant: dict[str, Any], task: dict[str, Any]
) -> dict[str, Any]:
    """Run one variant through the executor and property oracle."""
    system_prompt = variant["skill_text"]
    user_prompt = task["task_prompt"]
    try:
        result = executor.execute(system_prompt, user_prompt)
    except MissingCredentialError as exc:
        return {
            "variant_id": variant["variant_id"],
            "description": variant["description"],
            "status": "BLOCKED",
            "error": str(exc),
            "output": "",
            "observations": [],
            "model": getattr(executor, "model", "unknown"),
            "provider": getattr(executor, "provider", "unknown"),
        }
    except Exception as exc:
        return {
            "variant_id": variant["variant_id"],
            "description": variant["description"],
            "status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
            "output": "",
            "observations": [],
            "model": getattr(executor, "model", "unknown"),
            "provider": getattr(executor, "provider", "unknown"),
        }

    output = result.get("output", "")
    if not isinstance(output, str):
        return {
            "variant_id": variant["variant_id"],
            "description": variant["description"],
            "status": "ERROR",
            "error": (
                "executor returned non-text output: "
                f"{type(output).__name__}"
            ),
            "output": "",
            "observations": [],
            "model": result.get("model", getattr(executor, "model", "unknown")),
            "provider": result.get(
                "provider", getattr(executor, "provider", "unknown")
            ),
        }
    error = result.get("error")
    if error:
        return {
            "variant_id": variant["variant_id"],
            "description": variant["description"],
            "status": "ERROR",
            "error": error,
            "output": output,
            "observations": [],
            "model": result.get("model", ""),
            "provider": result.get("provider", ""),
            "temperature": result.get("temperature"),
            "max_tokens": result.get("max_tokens"),
            "usage": result.get("usage", {}),
            "response_id": result.get("response_id", ""),
            "finish_reason": result.get("finish_reason"),
            "truncated": result.get("truncated", False),
        }

    observations = run_property_oracle(output, task["properties"])

    return {
        "variant_id": variant["variant_id"],
        "description": variant["description"],
        "status": "COMPLETED",
        "error": error,
        "output": output,
        "output_digest": "sha256:" + hashlib.sha256(
            output.encode("utf-8")
        ).hexdigest(),
        "observations": observations,
        "model": result.get("model", ""),
        "provider": result.get("provider", ""),
        "temperature": result.get("temperature"),
        "max_tokens": result.get("max_tokens"),
        "usage": result.get("usage", {}),
        "response_id": result.get("response_id", ""),
        "finish_reason": result.get("finish_reason"),
        "truncated": result.get("truncated", False),
    }


def _executor_metadata(executor: Executor) -> dict[str, Any]:
    """Extract executor metadata for the report."""
    return {
        "type": type(executor).__name__,
        "model": getattr(executor, "model", "unknown"),
        "provider": getattr(executor, "provider", "unknown"),
        "temperature": getattr(executor, "temperature", None),
        "max_tokens": getattr(executor, "max_tokens", None),
        "available": getattr(executor, "is_available", lambda: True)(),
    }


def _summarize_differential(
    runs: list[dict[str, Any]],
    local_runs: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Summarize the differential across variants."""
    summary: dict[str, Any] = {
        "variants": len(runs),
        "by_status": {},
        "by_variant_property": {},
    }
    for run in runs:
        status = run["status"]
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
        if run["observations"]:
            props = {o["property_id"]: o["status"] for o in run["observations"]}
            summary["by_variant_property"][run["variant_id"]] = props

    if local_runs:
        summary["local_fallback"] = {
            "by_status": {},
            "by_variant_property": {},
        }
        for run in local_runs:
            status = run["status"]
            summary["local_fallback"]["by_status"][status] = (
                summary["local_fallback"]["by_status"].get(status, 0) + 1
            )
            if run["observations"]:
                props = {o["property_id"]: o["status"] for o in run["observations"]}
                summary["local_fallback"]["by_variant_property"][run["variant_id"]] = props

    summary["by_status"] = dict(sorted(summary["by_status"].items()))
    return summary


# ---------------------------------------------------------------------------
# Limitations
# ---------------------------------------------------------------------------

BEHAVIORAL_LIMITATIONS: list[dict[str, str]] = [
    {
        "check_class": "SEMANTIC_QUALITY",
        "reason": (
            "The property oracle checks specific deterministic properties, "
            "not semantic quality. A response that mentions 'finite budget' "
            "without understanding it would PASS P1."
        ),
    },
    {
        "check_class": "MODEL_STABILITY",
        "reason": (
            "Model outputs may vary across runs even at temperature 0. The "
            "behavioral differential records one observation per variant, not "
            "a statistical distribution."
        ),
    },
    {
        "check_class": "GENERALIZATION",
        "reason": (
            "The observation is tied to the pinned task, model, and runtime. "
            "It does not generalize beyond this specific configuration."
        ),
    },
]

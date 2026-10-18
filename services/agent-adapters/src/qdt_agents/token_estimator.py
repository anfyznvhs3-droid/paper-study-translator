from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

from qdt_agents.engine_contract import EngineRequest


def estimate_agent_tokens(
    request: EngineRequest,
    *,
    prompt_text: str = "",
    pricing: Mapping[str, float | int | Decimal] | None = None,
) -> dict[str, Any]:
    """Estimate tokens for Agent mode handoffs only.

    This intentionally does not estimate desktop worker or deterministic
    translator-core execution. It approximates English input as chars / 4 and
    Korean output as source tokens * 1.4. DUAL output includes both source and
    Korean output.
    """

    source_tokens = _english_char_tokens(_read_text(request.input_queue_path))
    profile_tokens = _english_char_tokens(_read_text(request.document_profile_path))
    prompt_tokens = _english_char_tokens(prompt_text)
    korean_output_tokens = int(source_tokens * 1.4)
    output_tokens = _output_tokens(request.output_mode, source_tokens, korean_output_tokens)

    estimate: dict[str, Any] = {
        "mode": "agent_only",
        "source_tokens": source_tokens,
        "profile_tokens": profile_tokens,
        "prompt_tokens": prompt_tokens,
        "korean_output_tokens": korean_output_tokens,
        "output_tokens": output_tokens,
        "total_tokens": source_tokens + profile_tokens + prompt_tokens + output_tokens,
        "cost_available": pricing is not None,
        "estimated_cost": None,
    }

    if pricing is not None:
        input_rate = Decimal(str(pricing.get("input_per_1k", 0)))
        output_rate = Decimal(str(pricing.get("output_per_1k", 0)))
        input_tokens = source_tokens + profile_tokens + prompt_tokens
        estimate["estimated_cost"] = float(
            (Decimal(input_tokens) / Decimal(1000) * input_rate)
            + (Decimal(output_tokens) / Decimal(1000) * output_rate)
        )

    return estimate


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _english_char_tokens(text: str) -> int:
    return int(len(text) / 4)


def _output_tokens(output_mode: str, source_tokens: int, korean_output_tokens: int) -> int:
    if output_mode.upper() == "DUAL":
        return source_tokens + korean_output_tokens
    return korean_output_tokens

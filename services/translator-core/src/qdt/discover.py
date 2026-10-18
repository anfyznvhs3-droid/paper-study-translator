"""Agent term-discovery response parser (task T2.4, testable slice).

Parses the JSON array response from the 2nd-pass agent discovery call.
Also provides orchestration for running discovery with an injected LLM.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qdt.memory import DomainMemoryStore

DISCOVERY_PROMPT = """You are a terminology reviewer for English→Korean {domain} document translation.
You are given the SOURCE (English), a DRAFT Korean TRANSLATION, and the CONFIRMED
glossary for this domain. Find terms that SHOULD be added to the domain glossary.

Focus on, in priority order:
1. Domain terms-of-art whose draft translation is FLUENT BUT WRONG for {domain}.
   Example: in a medical text, "control" rendered as "관리" when it should be "대조군".
   These are the most important — they are invisible to keyword scanners.
2. Terms left in English inside the Korean draft (residual).
3. Terms translated inconsistently across the document.

Do NOT propose:
- Anything already in the CONFIRMED glossary (listed below).
- General vocabulary a competent reader would translate the same way.
- URLs, DOIs, citation markers, units, proper nouns, numbers.

Be conservative. Over-proposing creates review fatigue. When unsure, use "low".

Output ONLY a JSON array, no prose. Each item:
{"source":"<english term>", "suggested_target":"<korean>", "reason":"<short why>", "confidence":"high|low"}
If nothing qualifies, output [].

DOMAIN: {domain}
CONFIRMED GLOSSARY: {glossary_json}
SOURCE:
{source_text}
DRAFT TRANSLATION:
{korean_text}"""


def format_discovery_prompt(
    domain: str,
    glossary: list[dict],
    source_text: str,
    korean_text: str,
) -> str:
    """Fill DISCOVERY_PROMPT placeholders using str.replace (NOT .format)."""
    glossary_json = json.dumps(glossary, ensure_ascii=False)
    return (
        DISCOVERY_PROMPT
        .replace("{domain}", domain)
        .replace("{glossary_json}", glossary_json)
        .replace("{source_text}", source_text)
        .replace("{korean_text}", korean_text)
    )


def run_discovery(
    store: "DomainMemoryStore",
    slug: str,
    source_text: str,
    korean_text: str,
    llm: callable,
) -> None:
    """Run discovery orchestration with an injected LLM callable."""
    glossary = [{"source": e.source, "target": e.target} for e in store.load_glossary(slug)]
    prompt = format_discovery_prompt(slug, glossary, source_text, korean_text)
    raw = llm(prompt)
    cands = parse_candidates(raw)
    for c in cands:
        store.record_decision(
            slug,
            c["source"],
            c["suggested_target"],
            status="candidate",
            confidence=c["confidence"],
            origin="agent",
        )


def parse_candidates(raw: str) -> list[dict]:
    """Parse agent discovery response into candidate dicts.

    Extracts first JSON array from surrounding prose, validates each item
    has required fields (source, suggested_target, confidence).
    """
    if not raw or not raw.strip():
        return []

    # Find first JSON array
    start = raw.find("[")
    if start == -1:
        return []

    # Find matching closing bracket
    depth = 0
    end = -1
    for i in range(start, len(raw)):
        if raw[i] == "[":
            depth += 1
        elif raw[i] == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end == -1:
        return []

    try:
        items = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return []

    if not isinstance(items, list):
        return []

    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if not item.get("source") or not item.get("suggested_target") or not item.get("confidence"):
            continue
        result.append({
            "source": item["source"],
            "suggested_target": item["suggested_target"],
            "reason": item.get("reason", ""),
            "confidence": item["confidence"],
        })

    return result


def agent_llm(engine: str, cli_path: str | None = None):
    """Build an LLM callable (prompt -> response) backed by a CLI agent engine.

    qdt_agents is imported lazily so this module loads without the adapters
    package on the path. The real engine call requires the agent CLI
    (codex/claude) installed; that behavior is verified at runtime (smoke),
    not in unit tests.
    """
    if engine == "codex":
        from qdt_agents.codex_cli import CodexCliEngine

        eng = CodexCliEngine(cli_path=cli_path or "codex")
    elif engine == "claude":
        from qdt_agents.claude_code_cli import ClaudeCodeCliEngine

        eng = ClaudeCodeCliEngine(cli_path=cli_path or "claude")
    else:
        raise ValueError(f"Unknown discovery engine: {engine!r} (use 'codex' or 'claude')")

    return lambda prompt: eng.complete(prompt)

"""Base CLI adapter for translation.

Shared logic for all CLI-based translation engines.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from qdt_agents.engine_contract import EngineRequest, EngineResult

logger = logging.getLogger(__name__)

# Codex CLI (and similar agentic CLIs) tend to respond conversationally
# ("send me the text", "understood, I'll handle...") to multi-paragraph,
# role-setup-style prompts with a labeled "Text to translate:" section.
# A single-sentence instruction ending with the text inline avoids that
# and reliably produces a direct translation from both Codex and Claude.
TRANSLATION_PROMPT = (
    "Translate the following text from {source_lang} to {target_lang} for a quality-management / "
    "automotive-QMS document (IATF 16949, FMEA, APQP, control plans). Preserve technical terminology, "
    "keep modal verbs (shall/must/should/may) precise, and keep abbreviations, numeric values, units, "
    "and references unchanged.{glossary_clause} Output ONLY the translated text with no explanations, "
    "labels, or extra text: {text}"
)


class BaseCliEngine(ABC):
    """Base class for CLI-based translation engines."""

    def __init__(self, cli_path: str | None, engine_name: str) -> None:
        # On Windows, npm-installed CLIs (codex, claude, ...) are .cmd shims that
        # subprocess can't launch by bare name without shell=True. Resolving to
        # the full path up front (e.g. codex.CMD) lets us keep shell=False.
        self.cli_path = (shutil.which(cli_path) or cli_path) if cli_path else None
        self.engine_name = engine_name

    @abstractmethod
    def build_cli_command(self, prompt: str) -> list[str]:
        """Build the CLI command to execute.

        Args:
            prompt: The translation prompt

        Returns:
            List of command arguments
        """
        ...

    def complete(self, prompt: str) -> str:
        """Send an arbitrary prompt to the CLI and return its text response.

        Generic prompt -> response. `translate` wraps this with a translation
        prompt; other callers (e.g. term discovery) supply their own prompt.
        """
        if not self.cli_path:
            raise RuntimeError(f"{self.engine_name} CLI is not configured")

        try:
            cmd = self.build_cli_command(prompt)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0:
                logger.error(f"{self.engine_name} CLI error: {result.stderr}")
                raise RuntimeError(f"{self.engine_name} CLI failed: {result.stderr}")

            output = result.stdout.strip()
            if not output:
                raise RuntimeError(f"{self.engine_name} CLI returned empty output")

            return output

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{self.engine_name} CLI timed out after 120 seconds")
        except FileNotFoundError:
            raise RuntimeError(f"{self.engine_name} CLI not found at: {self.cli_path}")

    def translate(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "ko",
        glossary: dict[str, str] | None = None,
    ) -> str:
        """Translate text using CLI."""
        glossary_clause = ""
        if glossary:
            glossary_text = "; ".join(f"{k} -> {v}" for k, v in glossary.items())
            glossary_clause = f" Use this glossary for these terms: {glossary_text}."

        prompt = TRANSLATION_PROMPT.format(
            source_lang=source_lang,
            target_lang=target_lang,
            text=text,
            glossary_clause=glossary_clause,
        )

        return self.complete(prompt)

    def run(self, request: EngineRequest) -> EngineResult:
        """Run translation for a queue request."""
        if not self.cli_path:
            return EngineResult(
                status="not_configured",
                message=f"{self.engine_name} CLI is not configured. Install and authenticate, then rerun.",
            )

        try:
            input_queue = json.loads(request.input_queue_path.read_text(encoding="utf-8"))
            output_queue = []

            glossary = None
            if request.glossary_path.exists():
                glossary = json.loads(request.glossary_path.read_text(encoding="utf-8"))

            for item in input_queue:
                source_text = item.get("source_text", "")
                if not source_text.strip():
                    item["translated_text"] = ""
                    output_queue.append(item)
                    continue

                translated = self.translate(
                    text=source_text,
                    source_lang=request.source_language,
                    target_lang=request.target_language,
                    glossary=glossary,
                )
                item["translated_text"] = translated
                output_queue.append(item)

            request.output_filled_queue_path.parent.mkdir(parents=True, exist_ok=True)
            request.output_filled_queue_path.write_text(
                json.dumps(output_queue, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            return EngineResult(
                status="completed",
                message=f"{self.engine_name} translated {len(output_queue)} items successfully.",
                filled_queue_path=request.output_filled_queue_path,
            )

        except Exception as e:
            logger.exception(f"{self.engine_name} translation failed: {e}")
            return EngineResult(
                status="failed",
                message=f"{self.engine_name} translation failed: {str(e)}",
            )

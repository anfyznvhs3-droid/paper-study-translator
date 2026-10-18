"""Codex CLI adapter for translation."""

from __future__ import annotations

import logging
import json
import os
import subprocess
import tempfile
from pathlib import Path

from qdt_agents.base_cli import BaseCliEngine

logger = logging.getLogger(__name__)

# Per-call timeout for a single Codex CLI invocation. Batches run concurrently
# (see qdt.agent_runner), so calls contend for the API and each takes longer than
# it would alone; 180s was too tight and killed otherwise-healthy runs near the
# end. The agent pipeline budget is 1200s, so a larger per-call cap is safe.
# Override with QDT_CODEX_CLI_TIMEOUT_SECS for slow networks / very dense batches.
def _codex_timeout_secs() -> int:
    raw = os.environ.get("QDT_CODEX_CLI_TIMEOUT_SECS")
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return 300

TRANSLATION_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["translations"],
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "source", "translation"],
                "properties": {
                    "id": {"type": "integer"},
                    "source": {"type": "string"},
                    "translation": {"type": "string"},
                },
            },
        },
    },
}


class CodexCliEngine(BaseCliEngine):
    """Codex CLI adapter for translation.

    Uses `codex exec -o <file>` instead of reading stdout: stdout interleaves
    session/progress logs with the response, but `-o`/`--output-last-message`
    writes only the agent's final reply.
    """

    def __init__(self, cli_path: str | None = "codex") -> None:
        super().__init__(cli_path, engine_name="Codex")

    def build_cli_command(self, prompt: str, output_file: str, schema_file: str | None = None) -> list[str]:
        command = [
            self.cli_path,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "-o",
            output_file,
        ]
        if schema_file:
            command.extend(["--output-schema", schema_file])
        command.append("-")
        return command

    def complete(self, prompt: str, output_schema: dict | None = None) -> str:
        if not self.cli_path:
            raise RuntimeError(f"{self.engine_name} CLI is not configured")

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as handle:
            output_path = Path(handle.name)
        schema_path: Path | None = None
        if output_schema is not None:
            with tempfile.NamedTemporaryFile(
                suffix=".schema.json",
                delete=False,
                mode="w",
                encoding="utf-8",
            ) as handle:
                json.dump(output_schema, handle)
                schema_path = Path(handle.name)

        timeout_secs = _codex_timeout_secs()
        try:
            cmd = self.build_cli_command(
                prompt,
                str(output_path),
                str(schema_path) if schema_path else None,
            )
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout_secs,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0:
                logger.error(f"{self.engine_name} CLI error: {result.stderr}")
                raise RuntimeError(f"{self.engine_name} CLI failed: {result.stderr}")

            output = output_path.read_text(encoding="utf-8").strip()
            if not output:
                raise RuntimeError(f"{self.engine_name} CLI returned empty output")

            return output
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"{self.engine_name} CLI timed out after {timeout_secs} seconds"
            )
        except FileNotFoundError:
            raise RuntimeError(f"{self.engine_name} CLI not found at: {self.cli_path}")
        finally:
            output_path.unlink(missing_ok=True)
            if schema_path:
                schema_path.unlink(missing_ok=True)

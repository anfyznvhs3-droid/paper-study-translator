"""Claude Code CLI adapter for translation."""

from __future__ import annotations

from qdt_agents.base_cli import BaseCliEngine


class ClaudeCodeCliEngine(BaseCliEngine):
    """Claude Code CLI adapter for translation."""

    def __init__(self, cli_path: str | None = "claude") -> None:
        super().__init__(cli_path, engine_name="Claude Code")

    def build_cli_command(self, prompt: str) -> list[str]:
        # `claude` takes the prompt as a positional argument, not --prompt.
        return [self.cli_path, "--print", "--output-format", "text", prompt]

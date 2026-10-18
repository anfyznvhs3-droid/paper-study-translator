from pathlib import Path

from qdt_agents.antigravity_agent import AntigravityAgentEngine
from qdt_agents.claude_code_cli import ClaudeCodeCliEngine
from qdt_agents.codex_cli import CodexCliEngine
from qdt_agents.engine_contract import EngineRequest
from qdt_agents.google_translate import GoogleTranslateDraftEngine


def _request(tmp_path: Path, engine_id: str) -> EngineRequest:
    queue = tmp_path / "queue.txt"
    queue.write_text("translate me", encoding="utf-8")
    return EngineRequest(
        engine_id=engine_id,
        document_profile_path=tmp_path / "profile.json",
        glossary_path=tmp_path / "glossary.csv",
        modal_policy_path=tmp_path / "modal.json",
        input_queue_path=queue,
        output_filled_queue_path=tmp_path / "filled.json",
        output_mode="DUAL",
        token_estimate_path=tmp_path / "tokens.json",
    )


def test_codex_cli_returns_failed_when_not_installed(tmp_path: Path) -> None:
    """A nonexistent CLI binary should fail cleanly via FileNotFoundError."""
    result = CodexCliEngine(cli_path="codex-does-not-exist-xyz").run(_request(tmp_path, "codex"))

    # CLI not installed → FileNotFoundError → "failed"
    assert result.status == "failed"
    assert "not found" in result.message.lower() or "failed" in result.message.lower()


def test_codex_cli_returns_not_configured_when_cli_missing(tmp_path: Path) -> None:
    result = CodexCliEngine(cli_path=None).run(_request(tmp_path, "codex"))

    assert result.status == "not_configured"
    assert "Codex" in result.message


def test_other_agent_stubs_return_not_configured(tmp_path: Path) -> None:
    engines = [
        AntigravityAgentEngine(),
        GoogleTranslateDraftEngine(),
    ]

    for engine in engines:
        result = engine.run(_request(tmp_path, "stub"))
        assert result.status == "not_configured"


def test_google_translate_stub_is_marked_draft_review_required(tmp_path: Path) -> None:
    result = GoogleTranslateDraftEngine().run(_request(tmp_path, "google-translate-draft"))

    assert "draft" in result.message.lower()
    assert "review-required" in result.message.lower()

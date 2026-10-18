from pathlib import Path

from qdt_agents.engine_contract import EngineRequest
from qdt_agents.token_estimator import estimate_agent_tokens


def _request(tmp_path: Path, output_mode: str = "DUAL") -> EngineRequest:
    queue = tmp_path / "queue.txt"
    queue.write_text("A" * 400, encoding="utf-8")
    profile = tmp_path / "profile.txt"
    profile.write_text("B" * 80, encoding="utf-8")

    return EngineRequest(
        engine_id="codex",
        document_profile_path=profile,
        glossary_path=tmp_path / "glossary.csv",
        modal_policy_path=tmp_path / "modal.json",
        input_queue_path=queue,
        output_filled_queue_path=tmp_path / "filled.json",
        output_mode=output_mode,
        token_estimate_path=tmp_path / "tokens.json",
    )


def test_agent_token_estimator_uses_documented_character_approximations(tmp_path: Path) -> None:
    estimate = estimate_agent_tokens(_request(tmp_path), prompt_text="C" * 40, pricing=None)

    assert estimate["mode"] == "agent_only"
    assert estimate["source_tokens"] == 100
    assert estimate["profile_tokens"] == 20
    assert estimate["prompt_tokens"] == 10
    assert estimate["korean_output_tokens"] == 140
    assert estimate["output_tokens"] == 240
    assert estimate["estimated_cost"] is None
    assert estimate["cost_available"] is False


def test_agent_token_estimator_only_counts_korean_output_for_ko_mode(tmp_path: Path) -> None:
    estimate = estimate_agent_tokens(_request(tmp_path, output_mode="KO"), prompt_text="", pricing=None)

    assert estimate["output_tokens"] == 140

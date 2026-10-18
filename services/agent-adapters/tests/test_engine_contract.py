from pathlib import Path

from qdt_agents.engine_contract import EngineRequest, EngineResult


def test_engine_request_defaults_capture_translation_contract() -> None:
    request = EngineRequest(
        engine_id="manual-fill",
        document_profile_path=Path("profile.json"),
        glossary_path=Path("glossary.csv"),
        modal_policy_path=Path("modal.json"),
        input_queue_path=Path("queue.json"),
        output_filled_queue_path=Path("filled.json"),
        output_mode="DUAL",
        token_estimate_path=Path("tokens.json"),
    )

    assert request.source_language == "en"
    assert request.target_language == "ko"
    assert request.engine_id == "manual-fill"
    assert request.output_mode == "DUAL"


def test_engine_result_warnings_default_to_independent_lists() -> None:
    first = EngineResult(status="completed", message="ok")
    second = EngineResult(status="waiting_for_import", message="pending")

    first.warnings.append("one")

    assert second.warnings == []

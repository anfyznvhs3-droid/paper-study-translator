from pathlib import Path

from qdt_agents.engine_contract import EngineRequest
from qdt_agents.manual_fill import ManualFillEngine


def _request(tmp_path: Path, filled_name: str = "filled.json") -> EngineRequest:
    return EngineRequest(
        engine_id="manual-fill",
        document_profile_path=tmp_path / "profile.json",
        glossary_path=tmp_path / "glossary.csv",
        modal_policy_path=tmp_path / "modal.json",
        input_queue_path=tmp_path / "queue.json",
        output_filled_queue_path=tmp_path / filled_name,
        output_mode="DUAL",
        token_estimate_path=tmp_path / "tokens.json",
    )


def test_manual_fill_completes_when_filled_queue_exists(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.output_filled_queue_path.write_text("[]", encoding="utf-8")

    result = ManualFillEngine().run(request)

    assert result.status == "completed"
    assert result.filled_queue_path == request.output_filled_queue_path


def test_manual_fill_waits_and_leaves_queue_location_available(tmp_path: Path) -> None:
    request = _request(tmp_path)

    result = ManualFillEngine().run(request)

    assert result.status == "waiting_for_import"
    assert result.filled_queue_path == request.output_filled_queue_path
    assert not request.output_filled_queue_path.exists()

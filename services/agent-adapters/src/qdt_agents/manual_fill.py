from __future__ import annotations

from qdt_agents.engine_contract import EngineRequest, EngineResult


class ManualFillEngine:
    """Manual import adapter for already-filled translation queues."""

    def run(self, request: EngineRequest) -> EngineResult:
        if request.output_filled_queue_path.exists():
            return EngineResult(
                status="completed",
                message="Filled queue already exists and is ready for import.",
                filled_queue_path=request.output_filled_queue_path,
            )

        return EngineResult(
            status="waiting_for_import",
            message="Filled queue is not present yet. Export/import location remains available.",
            filled_queue_path=request.output_filled_queue_path,
        )

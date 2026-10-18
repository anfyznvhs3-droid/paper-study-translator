from __future__ import annotations

from qdt_agents.engine_contract import EngineRequest, EngineResult


class AntigravityAgentEngine:
    """Safe placeholder for a future Antigravity agent adapter."""

    def run(self, request: EngineRequest) -> EngineResult:
        return EngineResult(
            status="not_configured",
            message=(
                "Antigravity Agent 어댑터가 아직 설정되지 않았습니다. 에이전트 실행 환경, 인증, "
                f"큐 입력({request.input_queue_path}) 및 filled queue 출력 경로({request.output_filled_queue_path})를 설정하세요."
            ),
            filled_queue_path=request.output_filled_queue_path,
        )

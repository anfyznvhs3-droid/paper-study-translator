from __future__ import annotations

from qdt_agents.engine_contract import EngineRequest, EngineResult


class GoogleTranslateDraftEngine:
    """Safe placeholder for Google Translate draft generation.

    Google Translate Draft output is never final quality-document translation;
    it must be reviewed and corrected by a qualified reviewer before import.
    """

    def run(self, request: EngineRequest) -> EngineResult:
        return EngineResult(
            status="not_configured",
            message=(
                "Google Translate Draft 어댑터가 아직 설정되지 않았습니다. Google API 키와 사용 정책을 설정하세요. "
                "이 엔진의 결과는 draft/review-required이며 최종 품질 문서 번역으로 사용할 수 없습니다."
            ),
            filled_queue_path=request.output_filled_queue_path,
            warnings=["draft/review-required", "not_final_quality_translation"],
        )

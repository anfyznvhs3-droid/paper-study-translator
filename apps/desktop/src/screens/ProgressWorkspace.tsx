import { cancelTranslation } from "../translation/translationBridge";
import { useEffect, useState } from "react";
import { ProgressList } from "../components/ProgressList";
import type { ProjectAction, ProjectState } from "../state/projectState";

interface ProgressWorkspaceProps {
  state: ProjectState;
  dispatch: React.Dispatch<ProjectAction>;
}

export function ProgressWorkspace({ state, dispatch }: ProgressWorkspaceProps) {
  const [monitorOpen, setMonitorOpen] = useState(false);
  const recentAgentFiles = state.agentStatus?.recent_files ?? [];
  const recentResponsePreview = state.agentStatus?.recent_response_preview?.trim();
  const activeFile = state.files.find((file) => file.id === state.activeJobId);
  const [cancelPending,setCancelPending] = useState(false);
  const [cancelMessage,setCancelMessage] = useState("");
  const [waitSeconds,setWaitSeconds] = useState(0);
  useEffect(() => {
    const start = Date.now();
    setWaitSeconds(0);
    const timer = window.setInterval(() => setWaitSeconds(Math.floor((Date.now()-start)/1000)),1000);
    return () => window.clearInterval(timer);
  },[activeFile?.id,state.translationRun?.stages.find((stage) => stage.status === "running")?.id]);
  async function stop() {
    setCancelPending(true);
    try {
      const accepted = await cancelTranslation();
      setCancelMessage(accepted ? "중지 요청을 전달했습니다. 실행 중인 프로세스가 끝나면 결과를 표시합니다." : "실행 중인 번역이 없습니다. 결과를 확인하는 중입니다.");
      if (!accepted) setCancelPending(false);
    } catch { setCancelMessage("중지 요청을 전달하지 못했습니다. 다시 시도하세요."); setCancelPending(false); }
  }

  useEffect(() => {
    if (state.translationMode !== "manual") {
      return;
    }

    if (!activeFile || activeFile.status !== "running") {
      return;
    }

    const timer = window.setTimeout(() => {
      dispatch({ type: "advanceMockJob" });
    }, 900);

    return () => window.clearTimeout(timer);
  }, [activeFile, dispatch, state.translationMode]);


  return (
    <section className="progress-workspace" aria-labelledby="progress-title">
      <div className="section-heading">
        <span>번역 진행</span>
        <h2 id="progress-title">문서 번역 중</h2>
      </div>

      {state.translationRun ? (
        <section className="engine-run" aria-label="번역 엔진 진행 상태">
          <div>
            <span>{state.translationRun.engineName}</span>
            <strong>{state.translationRun.summary}</strong>
          </div>
          <ol>
            {state.translationRun.stages.map((stage) => (
              <li key={stage.id} data-status={stage.status} aria-current={stage.status === "running" ? "step" : undefined}>
                <div className="stage-heading"><b>{stage.label}</b><span>{stage.status === "done" ? "단계 종료" : stage.status === "running" ? "진행 중" : "대기"}</span></div>
                <small>{stage.description}</small>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {state.agentStatus ? (
        <section className="agent-live-status" data-health={state.agentStatus.health} aria-label="Codex Agent 실제 진행 상태">
          <div>
            <span>Agent 작업 모니터 · {agentHealthLabel(state.agentStatus.health)}</span>
            <strong>
              완료 batch {state.agentStatus.completed_batches} / {state.agentStatus.total_batches || "?"}
            </strong>
          </div>
          <p>{agentProgressMessage(state.agentStatus)}</p>
          <dl>
            <div>
              <dt>완료 batch</dt>
              <dd>{state.agentStatus.completed_batches}개</dd>
            </div>
            <div>
              <dt>마지막 활동</dt>
              <dd>{state.agentStatus.last_activity_seconds}초 전</dd>
            </div>
            <div>
              <dt>중간 저장</dt>
              <dd>{state.agentStatus.workspace}</dd>
            </div>
          </dl>
          <button type="button" className="secondary-button agent-monitor-toggle" onClick={() => setMonitorOpen((open) => !open)}>
            {monitorOpen ? "모니터 접기" : "모니터 자세히 보기"}
          </button>
          {monitorOpen ? (
            <div className="agent-monitor-details">
              <div>
                <span>최근 파일</span>
                {recentAgentFiles.length > 0 ? (
                  <ul>
                    {recentAgentFiles.map((file) => (
                      <li key={file}>{file}</li>
                    ))}
                  </ul>
                ) : (
                  <p>아직 생성된 batch 파일이 없습니다.</p>
                )}
              </div>
              <div>
                <span>최근 응답 미리보기</span>
                <pre>{recentResponsePreview || "아직 완료된 response가 없습니다."}</pre>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      <p className="progress-wait-message">현재 단계 경과 {waitSeconds}초 · 전체 완료율은 아직 계산할 수 없습니다.</p>
      <button type="button" className="secondary-button cancel-job-button" onClick={() => void stop()} disabled={cancelPending}>
        {cancelPending ? "중지 처리 중" : "번역 중지"}
      </button>
      <p role={cancelMessage.includes("못했습니다") ? "alert" : "status"}>{cancelMessage}</p>
      <ProgressList files={state.files} />
    </section>
  );
}

function agentHealthLabel(health: NonNullable<ProjectState["agentStatus"]>["health"]) {
  switch (health) {
    case "active":
      return "Codex Agent 실행 중";
    case "waiting":
      return "Agent 응답 생성 중";
    case "stalled":
      return "정체 의심";
    case "paused":
      return "일시 중단됨";
    default:
      return "Agent 상태";
  }
}

function agentProgressMessage(status: NonNullable<ProjectState["agentStatus"]>) {
  const total = status.total_batches || "?";
  if (status.health === "paused") {
    return `처리 시간이 길어 일시 중단되었습니다. 완료 batch ${status.completed_batches} / ${total}까지 저장되어 있으며 중간 파일은 보존됐습니다. 다시 실행하면 새 작업을 시작합니다.`;
  }
  if (status.health === "stalled") {
    return `Codex 프로세스는 실행 중이지만 ${status.last_activity_seconds}초 동안 새 활동이 없습니다. 완료 batch ${status.completed_batches} / ${total}까지 저장되어 있습니다.`;
  }
  return `Codex Agent가 다음 batch 응답을 생성 중입니다. 완료 batch ${status.completed_batches} / ${total}, 마지막 활동 ${status.last_activity_seconds}초 전입니다.`;
}

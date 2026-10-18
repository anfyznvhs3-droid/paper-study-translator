import type { SourceFile } from "../state/projectState";

interface ProgressListProps {
  files: SourceFile[];
}

export function ProgressList({ files }: ProgressListProps) {
  const rows =
    files.length > 0
      ? files
      : [
          {
            id: "empty",
            name: "선택된 파일이 없습니다. 파일을 추가해 주세요.",
            pages: 0,
            status: "pending",
            progress: 0,
            kind: "file"
          } as SourceFile
        ];

  return (
    <div className="progress-list">
      {rows.map((file) => (
        <div className="progress-item" key={file.id}>
          <div className="progress-copy">
            <strong>{file.name}</strong>
            <span>
              {file.kind === "folder" ? "폴더" : "파일"} / {formatStatus(file.status)} / {file.sizeBytes ? "분량 추정 " + file.pages + "쪽" : "페이지 수 확인 전"}
            </span>
          </div>
          <div className={file.status === "running" ? "progress-meter is-indeterminate" : "progress-meter"}
            role="progressbar" aria-label={file.name}
            aria-valuemin={0} aria-valuemax={100}
            aria-valuenow={file.status === "completed" || file.status === "review_wait" ? 100 : undefined}
            aria-valuetext={file.status === "running" ? "처리 중, 완료율 확인 전" : formatStatus(file.status)}>
            <span style={{width:file.status === "running" ? "35%" : file.status === "completed" || file.status === "review_wait" ? "100%" : "0%"}} />
          </div>
          <b>{file.status === "running" ? "처리 중" : formatStatus(file.status)}</b>
        </div>
      ))}
    </div>
  );
}

function formatStatus(status: SourceFile["status"]) {
  switch (status) {
    case "pending":
      return "대기";
    case "running":
      return "진행 중";
    case "review_wait":
      return "검수 대기";
    case "completed":
      return "완료";
    case "failed":
      return "실패";
    case "cancelled":
      return "중지됨";
    case "skipped":
      return "미실행";
    case "paused":
      return "일시 중단";
    default:
      return status;
  }
}

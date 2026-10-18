import { Select } from "../components/Select";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { useState, type ChangeEvent } from "react";
import type { ProjectState } from "../state/projectState";

interface PdfCaptureResult {
  ok: boolean;
  message: string;
  page: number;
  image_path: string;
  data_url: string;
}

const defaultCreatorEmail = "";

export function FeedbackWorkspace({ state }: { state: ProjectState }) {
  const [creatorEmail, setCreatorEmail] = useState(defaultCreatorEmail);
  const [category, setCategory] = useState("번역 품질");
  const [pdfPath, setPdfPath] = useState("");
  const [page, setPage] = useState(1);
  const [message, setMessage] = useState("");
  const [capture, setCapture] = useState<PdfCaptureResult | null>(null);
  const [status, setStatus] = useState("");
  const [hasError, setHasError] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);

  const capturePdf = async () => {
    setHasError(false);
    setIsCapturing(true);
    setStatus("");
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: "PDF", extensions: ["pdf"] }]
      });
      if (!selected || Array.isArray(selected)) {
        setIsCapturing(false);
        return;
      }

      setPdfPath(selected);
      setCapture(null);
      const result = await invoke<PdfCaptureResult>("capture_pdf_page_snapshot", {
        request: { pdf_path: selected, page }
      });
      if (!result.ok) throw new Error(result.message);
      setCapture(result);
      setStatus(`PDF ${result.page}페이지 캡처 완료`);
    } catch (error) {
      setHasError(true);
      setStatus(`PDF 캡처 실패: ${String(error)}`);
    } finally {
      setIsCapturing(false);
    }
  };

  const openMailDraft = () => {
    const subject = `[QDT Feedback] ${category} - ${state.projectName}`;
    const body = [
      "불편 사항",
      message.trim() || "(내용을 입력하세요)",
      "",
      "분류",
      category,
      "",
      "프로젝트",
      state.projectName,
      "",
      "PDF",
      pdfPath || "(선택 안 됨)",
      "",
      "캡처",
      capture ? `${capture.image_path} (${capture.page}페이지)` : "(캡처 안 됨)",
      "",
      "현재 설정",
      `모드: ${state.translationMode}, 엔진: ${state.engine}, 출력: ${state.outputMode}, 검수: ${state.reviewMode}, 품질: ${state.quality}`
    ].join("\n");

    window.location.href = `mailto:${encodeURIComponent(creatorEmail)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  };

  const updatePage = (event: ChangeEvent<HTMLInputElement>) => {
    const nextPage = Number.parseInt(event.currentTarget.value, 10);
    setPage(Number.isFinite(nextPage) ? Math.max(1, nextPage) : 1);
  };

  return (
    <section className="setup-panel workbench-only feedback-workspace" aria-label="피드백">
      <div className="section-heading">
        <span>피드백</span>
        <h2>피드백 작성</h2>
      </div>

      <div className="setup-step">
        <div className="step-copy">
          <span>문제 기록</span>
          <h3>문제 내용을 메일 초안으로 정리합니다</h3>
          <p>PDF 캡처는 이 PC에 PNG로 저장합니다. 메일 작성은 초안만 열며 파일이 자동 첨부되지는 않습니다. 받는 주소와 첨부 파일을 확인한 뒤 직접 전송하세요.</p>
        </div>

        <form onSubmit={(event) => { event.preventDefault(); openMailDraft(); }}>
        <p id="feedback-recipient-help" className="mode-subtext">메일 초안을 열려면 받는 사람의 실제 이메일 주소를 입력하세요.</p>
        <div className="feedback-form-grid">
          <label className="text-field">
            <span>분류</span>
            <Select label="분류" value={category} onChange={setCategory} options={["번역 품질","레이아웃 깨짐","PDF 캡처 문제","앱 사용성","기타"].map(label=>({value:label,label}))} />
          </label>

          <label className="text-field">
            <span>받는 사람 이메일</span>
            <input type="email" required value={creatorEmail} placeholder="받는 사람의 실제 이메일 주소" onChange={(event) => setCreatorEmail(event.currentTarget.value)} aria-describedby="feedback-recipient-help" />
          </label>

          <label className="text-field">
            <span>PDF 페이지</span>
            <input type="number" min="1" value={page} onChange={updatePage} />
          </label>
        </div>

        <label className="text-field feedback-message-field">
          <span>내용</span>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.currentTarget.value)}
            placeholder="어떤 페이지에서 무엇이 불편했는지 적어주세요."
          />
        </label>

        <div className="feedback-actions">
          <button type="button" className="secondary-button" onClick={() => void capturePdf()} disabled={isCapturing}>
            {isCapturing ? "캡처 중" : "PDF 캡처하기"}
          </button>
          <button type="submit" className="primary-button">
            메일 작성하기
          </button>
        </div>

        </form>
        {status ? <p className="mode-subtext" role={hasError ? "alert" : "status"}>{status}</p> : null}
      </div>

      {capture ? (
        <div className="setup-step feedback-capture-preview">
          <div className="step-copy">
            <span>캡처</span>
            <h3>{capture.page}페이지 캡처</h3>
            <p>{capture.image_path}</p>
          </div>
          <img src={capture.data_url} alt={`${capture.page}페이지 PDF 캡처`} />
        </div>
      ) : null}
    </section>
  );
}

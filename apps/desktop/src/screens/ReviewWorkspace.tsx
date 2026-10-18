import { Icon } from "../components/Icon";
import { persistReviewSession } from "../translation/reviewSession";
import { pdfResults, fileLabel } from "../translation/pdfResults";
import { SummaryCards } from "../components/SummaryCards";
import { projectReducer } from "../state/projectState";
import { useCallback, useEffect, useMemo, useState, type Dispatch } from "react";
import type { ProjectAction, ProjectState, ReviewItem } from "../state/projectState";
import { addTerm, listCandidates, listGlossary, promote, reject, type Candidate, type GlossaryEntry } from "../translation/wikiBridge";

interface ReviewWorkspaceProps {
  state: ProjectState;
  dispatch: Dispatch<ProjectAction>;
}

interface ReviewArtifact {
  label: string;
  path?: string;
  role: string;
}

const modalReviewPoints = [
  { source: "shall / must", target: "필수 요구사항 또는 강한 의무로 유지", type: "필수성" },
  { source: "should", target: "권고 표현으로 유지", type: "권고성" },
  { source: "may / can", target: "허용과 가능성을 구분", type: "허용성" },
  { source: "uppercase acronym", target: "한국어(원문 약어) 형태로 추적성 유지", type: "추적성" }
];

const REVIEW_PAGE_SIZE = 10;

export function ReviewWorkspace({ state, dispatch }: ReviewWorkspaceProps) {
  const [saving,setSaving] = useState(false);
  const [saveError,setSaveError] = useState("");
  async function commit(action: ProjectAction) {
    if(saving)return;
    setSaving(true);setSaveError("");
    try {
      const next=projectReducer(state,action);
      await persistReviewSession(next);
      dispatch(action);
    } catch(error) { setSaveError("검수 결정을 저장하지 못했습니다: "+String(error)); }
    finally {setSaving(false);}
  }
  const domain = state.domain;
  const result = state.lastRunResult;
  const artifacts = classifyArtifacts(result?.outputFiles ?? []);
  // Review data is internal; only PDFs are public deliverables.
  const presentArtifacts = artifacts.filter((artifact) => artifact.path);
  const reviewItems = result?.reviewItems ?? [];
  const reviewCandidates = reviewItems.filter((item) => item.status === "open");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [reviewPage, setReviewPage] = useState(0);
  const reviewPageCount = Math.max(1, Math.ceil(reviewCandidates.length / REVIEW_PAGE_SIZE));
  const safeReviewPage = Math.min(reviewPage, reviewPageCount - 1);
  const reviewPageStart = safeReviewPage * REVIEW_PAGE_SIZE;
  const reviewPageEnd = Math.min(reviewPageStart + REVIEW_PAGE_SIZE, reviewCandidates.length);
  const visibleReviewCandidates = reviewCandidates.slice(reviewPageStart, reviewPageEnd);
  const visibleReviewKeys = visibleReviewCandidates.map(toReviewItemKey);
  const selectedItem = reviewCandidates[Math.min(selectedIndex, Math.max(0, reviewCandidates.length - 1))];
  const reviewPoints = state.translationRun?.reviewPoints.length ? state.translationRun.reviewPoints : modalReviewPoints;
  const hasRealResult = Boolean(result?.outputFiles.length || reviewItems.length);
  const candidateSummary = useMemo(() => summarizeCandidates(reviewItems), [reviewItems]);
  const hasReviewCandidates = reviewCandidates.length > 0;
  const reviewRangeLabel = hasReviewCandidates
    ? `${reviewPageStart + 1}-${reviewPageEnd} / ${reviewCandidates.length}`
    : "0 / 0";
  const reviewProgress =
    reviewItems.length > 0 ? Math.round((candidateSummary.candidates / reviewItems.length) * 100) : 0;

  const [wikiCandidates, setWikiCandidates] = useState<Candidate[]>([]);
  const [wikiLoading, setWikiLoading] = useState(false);

  const refreshWiki = useCallback(async () => {
    try {
      const cands = await listCandidates(domain);
      setWikiCandidates(cands);
    } catch (err) {
      console.warn("[wiki] load candidates failed:", err);
    }
  }, [domain]);

  useEffect(() => {
    void refreshWiki();
  }, [refreshWiki]);

  const [glossary, setGlossary] = useState<GlossaryEntry[]>([]);
  const [glossaryQuery, setGlossaryQuery] = useState("");

  const refreshGlossary = useCallback(async () => {
    try {
      setGlossary(await listGlossary(domain));
    } catch (err) {
      console.warn("[glossary] load failed:", err);
    }
  }, [domain]);

  useEffect(() => {
    void refreshGlossary();
  }, [refreshGlossary]);

  useEffect(() => {
    setSelectedIndex((index) => Math.min(index, Math.max(0, reviewCandidates.length - 1)));
  }, [reviewCandidates.length]);

  useEffect(() => {
    setReviewPage((page) => Math.min(page, Math.max(0, reviewPageCount - 1)));
  }, [reviewPageCount]);

  useEffect(() => {
    if (!hasReviewCandidates) {
      setSelectedIndex(0);
      return;
    }

    setSelectedIndex((index) =>
      index < reviewPageStart || index >= reviewPageEnd ? reviewPageStart : Math.min(index, reviewCandidates.length - 1)
    );
  }, [hasReviewCandidates, reviewCandidates.length, reviewPageEnd, reviewPageStart]);

  const handlePromote = async (source: string) => {
    setWikiLoading(true);
    try {
      await promote(domain, source);
      await refreshWiki();
    } catch (err) {
      console.warn("[wiki] promote failed:", err);
    } finally {
      setWikiLoading(false);
    }
  };

  const handleReject = async (source: string) => {
    setWikiLoading(true);
    try {
      await reject(domain, source);
      await refreshWiki();
    } catch (err) {
      console.warn("[wiki] reject failed:", err);
    } finally {
      setWikiLoading(false);
    }
  };

  const [quickSource, setQuickSource] = useState("");
  const [quickTarget, setQuickTarget] = useState("");
  const [quickNotes, setQuickNotes] = useState("");
  const [quickLoading, setQuickLoading] = useState(false);
  const [quickMessage, setQuickMessage] = useState<string | null>(null);
  const [quickAddOpen, setQuickAddOpen] = useState(false);

  const quickNotesDefault = selectedItem ? `검수 중 추가 (p.${selectedItem.page || "-"})` : "검수 중 추가";

  const handleQuickAdd = async () => {
    const source = quickSource.trim();
    const target = quickTarget.trim();
    if (!source || !target) return;

    setQuickLoading(true);
    setQuickMessage(null);
    try {
      await addTerm(domain, source, target, quickNotes.trim() || quickNotesDefault);
      setQuickMessage(`"${source}" → "${target}" 용어집에 추가됨`);
      setQuickSource("");
      setQuickTarget("");
      setQuickNotes("");
      await refreshGlossary();
    } catch (err) {
      console.warn("[wiki] quick add failed:", err);
      setQuickMessage("추가에 실패했습니다.");
    } finally {
      setQuickLoading(false);
    }
  };

  const handlePrepareQuickTerm = () => {
    if (!selectedItem) return;

    setQuickSource(selectedItem.source_text);
    setQuickTarget(selectedItem.translated_text ?? "");
    setQuickNotes(quickNotesDefault);
    setQuickMessage(null);
    setQuickAddOpen(true);
  };

  const handleDeferSelected = () => {
    setSelectedIndex((index) => Math.min(reviewCandidates.length - 1, index + 1));
  };

  const glossaryView = useMemo(() => {
    const segment = (selectedItem?.source_text ?? "").toLowerCase();
    const q = glossaryQuery.trim().toLowerCase();
    const matchesQuery = (entry: GlossaryEntry) =>
      !q ||
      entry.source.toLowerCase().includes(q) ||
      entry.target.toLowerCase().includes(q) ||
      (entry.notes ?? "").toLowerCase().includes(q);
    const inSegment = (entry: GlossaryEntry) =>
      entry.source.trim().length > 0 && segment.includes(entry.source.toLowerCase());
    const filtered = glossary.filter(matchesQuery);
    const relevant = filtered.filter(inSegment);
    const rest = filtered.filter((entry) => !inSegment(entry));
    return { relevant, ordered: [...relevant, ...rest], relevantCount: relevant.length };
  }, [glossary, glossaryQuery, selectedItem]);

  return (
    <section className="review-workspace review-only" aria-labelledby="review-title">
      <div className="review-main">
        <div className="review-toolbar">
          <div className="section-heading">
            <span>검수 ON</span>
            <h2 id="review-title">실제 번역 결과 검수</h2>
          </div>
          <div className="review-actions">
            <button
              type="button"
              className="secondary-button"
              disabled={!hasReviewCandidates || safeReviewPage === 0}
              onClick={() => setReviewPage((page) => Math.max(0, page - 1))}
            >
              이전 10개
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={!hasReviewCandidates || safeReviewPage >= reviewPageCount - 1}
              onClick={() => setReviewPage((page) => Math.min(reviewPageCount - 1, page + 1))}
            >
              다음 10개
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => void commit({ type: "approveReviewItems", keys: visibleReviewKeys })}
              disabled={saving || visibleReviewKeys.length === 0}
            >
              현재 {visibleReviewKeys.length}건 문제없음
            </button>
            <button
              type="button"
              className="secondary-button danger-button"
              onClick={() => void commit({ type: "approveAllReviewItems" })}
              disabled={saving || reviewCandidates.length === 0}
            >
              전체 문제없음 처리
            </button>
            <button type="button" className="primary-button" onClick={() => void commit({ type: "completeReview" })} disabled={saving || !hasRealResult || reviewCandidates.length > 0}>
              검수 종료
            </button>
          </div>
        </div>

        <p role="status">{saving ? "검수 결정을 저장하고 있습니다." : reviewCandidates.length ? "미해결 후보를 확인해야 검수를 종료할 수 있습니다. 결정은 이 PC의 작업 기록에 저장됩니다." : "남은 자동 후보가 없습니다. 최종 PDF를 직접 확인한 뒤 검수를 종료하세요."}</p>
        <p className="review-scope-note">자동 후보는 전체 문서의 번역 누락을 모두 찾아내지 못합니다. ‘문제없음’은 확인 기록만 저장하며 PDF를 수정하거나 재번역하지 않습니다.</p>
        {selectedItem && /\{v\d+\}/.test(selectedItem.source_text) ? <p className="review-scope-note">이 항목에는 보존 구간 표시가 있습니다. 표시 안의 실제 문장은 이 화면에서 검사되지 않으므로 원문과 최종 PDF를 직접 대조하세요.</p> : null}
        {saveError ? <p role="alert">{saveError}</p> : null}
        {!hasRealResult ? (
          <section className="review-empty">
            <strong>아직 실제 번역 결과가 없습니다.</strong>
            <span>검수 ON 화면은 실제 파일 번역이 끝난 뒤 생성된 PDF, MD, HTML, audit 데이터를 기준으로 열립니다.</span>
          </section>
        ) : null}

        <SummaryCards label="검수 요약" items={[
          {label:"확인 필요",value:reviewCandidates.length,unit:"개"},
          {label:"후보 확인률",value:reviewItems.length?reviewProgress:"집계 없음",unit:reviewItems.length?"%":undefined,textValue:!reviewItems.length},
          {label:"확인한 후보",value:candidateSummary.candidates,unit:"개"},
          {label:"표준 용어",value:glossary.length,unit:"개"}
        ]} />

        <div className="review-compare-grid">
          <aside className="review-candidate-list" aria-label="검수 후보">
            <div className="pane-heading">
              <span>확인할 문장</span>
              <b>{reviewRangeLabel}</b>
            </div>
            {hasReviewCandidates ? (
              visibleReviewCandidates.map((item, index) => (
                <button
                  type="button"
                  key={`${item.page}-${reviewPageStart + index}-${item.source_text}`}
                  aria-pressed={reviewPageStart + index === selectedIndex}
                  className={reviewPageStart + index === selectedIndex ? "is-selected" : ""}
                  onClick={() => setSelectedIndex(reviewPageStart + index)}
                >
                  <span>{reviewCandidateKind(item)} · p.{item.page || "-"}</span>
                  <strong>{item.source_text}</strong>
                  {item.translated_text ? <em>{item.translated_text}</em> : null}
                  <small>{item.status === "open" ? "확인 필요" : item.reason}</small>
                </button>
              ))
            ) : (
              <p className="review-empty-copy">검수할 자동 후보가 없습니다.</p>
            )}
          </aside>

          {hasReviewCandidates ? (
            <div className="review-comparison-shell">
              <section className="review-decision-bar" aria-label="현재 항목 빠른 판단">
                <div className="pane-heading">
                  <span>현재 항목 판단</span>
                  <b>{selectedItem ? `${reviewCandidateKind(selectedItem)} · p.${selectedItem.page || "-"}` : "선택 없음"}</b>
                </div>
                <div className="review-decision-actions">
                  <button
                    type="button"
                    className="primary-button"
                    onClick={() => void commit({ type: "approveReviewItems", keys: selectedItem ? [toReviewItemKey(selectedItem)] : [] })}
                    disabled={saving || !selectedItem}
                  >
                    문제없음
                  </button>
                  <button type="button" className="secondary-button" onClick={handlePrepareQuickTerm} disabled={!selectedItem}>
                    용어로 등록
                  </button>
                  <button type="button" className="secondary-button" onClick={handleDeferSelected} disabled={!selectedItem}>
                    나중에 다시 보기
                  </button>
                </div>
              </section>

              {selectedItem?.source_path ? <p className="review-source-path" title={selectedItem.source_path}>검수 문서 <strong>{selectedItem.source_path.split(/[\\/]/).pop()}</strong></p> : null}
              <div className="review-comparison">
                <article className="text-pane">
                  <div className="pane-heading">
                    <span>원문</span>
                  </div>
                  <p>{selectedItem?.source_text ?? ""}</p>
                </article>

                <article className="text-pane is-korean">
                  <div className="pane-heading">
                    <span>번역문</span>
                  </div>
                  <p>{selectedItem?.translated_text ?? ""}</p>
                </article>
              </div>
            </div>
          ) : (
            <section className="review-clean-state" aria-label="자동 검수 후보 없음">
              <strong>검수할 자동 후보가 없습니다.</strong>
              <span>자동 후보가 없다는 것은 번역 누락이나 오류가 없다는 뜻이 아닙니다. 최종 PDF를 열어 확인하세요.</span>
            </section>
          )}
        </div>

        {quickAddOpen ? (
          <section className="term-review review-quick-add" aria-label="용어 등록">
            <div className="card-heading">
              <h3>용어 등록</h3>
              <span>현재 항목에서 발견한 표현을 표준 용어로 저장</span>
            </div>
            {selectedItem ? (
              <p className="mode-subtext">
                참고: p.{selectedItem.page || "-"} — {selectedItem.reason}
              </p>
            ) : null}
            <div className="feedback-form-grid">
              <label className="text-field">
                <span>원문</span>
                <input value={quickSource} onChange={(e) => setQuickSource(e.currentTarget.value)} placeholder="Failure Mode" />
              </label>
              <label className="text-field">
                <span>번역문</span>
                <input value={quickTarget} onChange={(e) => setQuickTarget(e.currentTarget.value)} placeholder="고장 형태" />
              </label>
              <label className="text-field">
                <span>메모</span>
                <input value={quickNotes} onChange={(e) => setQuickNotes(e.currentTarget.value)} placeholder={quickNotesDefault} />
              </label>
            </div>
            <div className="feedback-actions">
              {quickMessage ? <span className="mode-subtext">{quickMessage}</span> : null}
              <button type="button" className="secondary-button" onClick={() => setQuickAddOpen(false)}>
                용어 등록 닫기
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={() => void handleQuickAdd()}
                disabled={quickLoading || !quickSource.trim() || !quickTarget.trim()}
              >
                용어 추가
              </button>
            </div>
          </section>
        ) : null}

        <section className="term-review glossary-reference" aria-label="표준 용어집 참조">
            <div className="card-heading">
              <h3>표준 용어집 참조</h3>
              <span>
                {glossaryView.relevantCount > 0
                  ? `이 문단 ${glossaryView.relevantCount}개 · 전체 ${glossary.length}개`
                  : `전체 ${glossary.length}개`}
              </span>
            </div>
            <label className="text-field glossary-search">
              <span>검색</span>
              <input
                value={glossaryQuery}
                onChange={(e) => setGlossaryQuery(e.currentTarget.value)}
                placeholder="원문 / 번역 / 메모로 검색"
              />
            </label>
            {glossary.length === 0 ? (
              <p className="mode-subtext">표준 용어집에 등록된 용어가 없습니다. 빠른 용어 추가로 등록하면 여기에 바로 나타납니다.</p>
            ) : glossaryView.ordered.length === 0 ? (
              <p className="mode-subtext">검색 결과가 없습니다.</p>
            ) : (
              <div className="term-table glossary-table" role="table" aria-label="표준 용어집">
                <div className="term-row term-head" role="row">
                  <span role="columnheader">원문</span>
                  <span role="columnheader">번역</span>
                  <span role="columnheader">메모</span>
                </div>
                {glossaryView.ordered.map((entry) => (
                  <div
                    className={glossaryView.relevant.includes(entry) ? "term-row is-in-segment" : "term-row"}
                    role="row"
                    key={entry.source}
                  >
                    <span role="cell">{entry.source}</span>
                    <strong role="cell">{entry.target}</strong>
                    <em role="cell">{entry.notes || "-"}</em>
                  </div>
                ))}
              </div>
            )}
          </section>

        <div className="review-lower-grid">
        <section className="term-review">
          <div className="card-heading">
            <h3>검수 파일</h3>
            <span>실제 생성 파일</span>
          </div>
          <div className="review-artifacts">
            {presentArtifacts.length > 0 ? (
              presentArtifacts.map((artifact) => (
                <div key={artifact.label}>
                  <span>{artifact.label}</span>
                  <strong>{artifact.role}</strong>
                  <code>{artifact.path}</code>
                </div>
              ))
            ) : (
              <p className="mode-subtext">생성된 검수 파일이 없습니다.</p>
            )}
          </div>
        </section>

        <section className="term-review">
          <div className="card-heading">
            <h3>검수 기준</h3>
            <span>원문 의미와 비교</span>
          </div>
          <details className="review-standards-details">
            <summary className="mode-subtext">모달 표현 기준 펼치기<Icon name="chevron" className="disclosure-icon" /></summary>
          <div className="term-table review-standards-table" role="table" aria-label="검수 기준">
            <div className="term-row term-head" role="row">
              <span role="columnheader">원문 신호</span>
              <span role="columnheader">확인할 번역</span>
              <span role="columnheader">구분</span>
            </div>
            {reviewPoints.map((term) => (
              <div className="term-row" role="row" key={`${term.source}-${term.type}`}>
                <span role="cell">{term.source}</span>
                <strong role="cell" title={reviewNote(term)}>
                  {term.target}
                </strong>
                <em role="cell">{term.type}</em>
              </div>
            ))}
          </div>
          </details>
        </section>

        {wikiCandidates.length > 0 ? (
        <section className="term-review">
          <div className="card-heading">
            <h3>WIKI 후보 용어</h3>
            <span>{wikiCandidates.length}개 대기</span>
          </div>
          {(
            <div className="term-table wiki-candidate-table" role="table" aria-label="WIKI 후보">
              <div className="term-row term-head" role="row">
                <span role="columnheader">원문</span>
                <span role="columnheader">번역</span>
                <span role="columnheader">신호</span>
                <span role="columnheader">승인</span>
                <span role="columnheader">거부</span>
              </div>
              {wikiCandidates.map((cand) => (
                <div className="term-row" role="row" key={cand.source}>
                  <span role="cell">{cand.source}</span>
                  <strong role="cell">{cand.target || "-"}</strong>
                  <em role="cell">{cand.signal || cand.origin}</em>
                  <span role="cell">
                    <button type="button" className="secondary-button" onClick={() => void handlePromote(cand.source)} disabled={wikiLoading}>승인</button>
                  </span>
                  <span role="cell">
                    <button type="button" className="secondary-button" onClick={() => void handleReject(cand.source)} disabled={wikiLoading}>거부</button>
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
        ) : null}
        </div>
      </div>
    </section>
  );
}

function summarizeCandidates(items: ReviewItem[]) {
  return {
    needsReview: items.filter((item) => item.status === "open").length,
    candidates: items.filter((item) => item.status !== "open").length
  };
}

function toReviewItemKey(item: ReviewItem) {
  return {
    source_path: item.source_path,
    page: item.page,
    kind: item.kind,
    source_text: item.source_text,
    translated_text: item.translated_text
  };
}

function reviewCandidateKind(item: ReviewItem) {
  if (item.kind === "translation_incomplete") return "번역 미완료";
  if (item.kind === "image_ocr") return "그림 OCR";
  if (item.kind === "table_overlay") return "표 번역";
  if (item.kind === "native_repair") return "누락 보정";
  if (item.kind === "untranslated_region" || item.kind === "untranslated_source_sentence") return "미번역 확인";
  if (item.kind === "audit_unavailable") return "검수 기록 오류";
  const source = item.source_text.trim();
  const wordCount = source.split(/\s+/).filter(Boolean).length;
  if (item.kind === "term_mismatch" || item.kind === "acronym_inconsistent") {
    return "용어 후보";
  }
  if (item.kind === "layout_overflow" || item.kind === "table_cell_error" || item.kind === "figure_label_error") {
    return "레이아웃 확인";
  }
  if (wordCount <= 6 || /^[A-Z0-9\s:;.,\-–—/()]+$/.test(source)) {
    return "제목/라벨";
  }
  return "본문";
}

function classifyArtifacts(paths: string[]): ReviewArtifact[] {
  return pdfResults(paths).map(path=>({label:fileLabel(path),path,role:"번역 PDF"}));
}

function reviewNote(term: unknown) {
  if (!term || typeof term !== "object" || !("note" in term)) {
    return undefined;
  }

  const note = (term as { note?: unknown }).note;
  return typeof note === "string" ? note : undefined;
}

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const reviewWorkspacePath = fileURLToPath(
  new URL("../src/screens/ReviewWorkspace.tsx", import.meta.url)
);
const globalCssPath = fileURLToPath(new URL("../src/styles/global.css", import.meta.url));

test("review workspace does not equate zero candidates with verified translation quality", () => {
  const source = readFileSync(reviewWorkspacePath, "utf8");

  assert.match(source, /검수할 자동 후보가 없습니다\./);
  assert.match(source, /자동 후보가 없다는 것은 번역 누락이나 오류가 없다는 뜻이 아닙니다/);
  assert.doesNotMatch(source, /audit 파일이 포함됐는지 확인하세요/);
});

test("review workspace uses standard glossary wording consistently", () => {
  const source = readFileSync(reviewWorkspacePath, "utf8");

  assert.match(source, /aria-label="표준 용어집 참조"/);
  assert.match(source, /<h3>표준 용어집 참조<\/h3>/);
  assert.match(source, /표준 용어집에 등록된 용어가 없습니다/);
  assert.match(source, /role="table" aria-label="표준 용어집"/);
  assert.doesNotMatch(source, /확정 용어집/);
  assert.doesNotMatch(source, /확정된 용어/);
});

test("review workspace supports bulk approval for large review queues", () => {
  const source = readFileSync(reviewWorkspacePath, "utf8");

  assert.match(source, /전체 문제없음 처리/);
  assert.match(source, /approveAllReviewItems/);
  assert.match(source, /item\.status === "open"/);
  assert.doesNotMatch(source, /후보 전체 확인/);
});

test("review workspace paginates review candidates in batches of ten", () => {
  const source = readFileSync(reviewWorkspacePath, "utf8");

  assert.match(source, /const REVIEW_PAGE_SIZE = 10/);
  assert.match(source, /이전 10개/);
  assert.match(source, /다음 10개/);
  assert.match(source, /문제없음/);
  assert.match(source, /현재 \{visibleReviewKeys.length\}건 문제없음/);
  assert.match(source, /approveReviewItems/);
  assert.match(source, /visibleReviewCandidates/);
  assert.doesNotMatch(source, /현재 항목 확인/);
  assert.doesNotMatch(source, /현재 10개 확인/);
});

test("review workspace uses reviewer-facing Korean labels", () => {
  const source = readFileSync(reviewWorkspacePath, "utf8");

  assert.match(source, /확인할 문장/);
  assert.match(source, /현재 항목 판단/);
  assert.match(source, /원문/);
  assert.match(source, /번역문/);
  assert.match(source, /용어로 등록/);
  assert.match(source, /나중에 다시 보기/);
  assert.match(source, /확인 필요/);
  assert.match(source, /후보 확인률/);
  assert.match(source, /검수 종료/);
  assert.doesNotMatch(source, />Review Queue</);
  assert.doesNotMatch(source, />Original</);
  assert.doesNotMatch(source, />Korean</);
  assert.doesNotMatch(source, /원문 \(source\)/);
  assert.doesNotMatch(source, /번역 \(target\)/);
  assert.doesNotMatch(source, /메모 \(notes\)/);
  assert.doesNotMatch(source, /검수 완료/);
});

test("review workspace keeps item decisions with the comparison instead of stretching to queue height", () => {
  const source = readFileSync(reviewWorkspacePath, "utf8");
  const css = readFileSync(globalCssPath, "utf8");

  assert.match(source, /className="review-decision-bar"/);
  assert.match(source, /aria-label="현재 항목 빠른 판단"/);
  assert.match(source, /className="review-decision-bar"[\s\S]*?className="review-comparison"/);
  assert.doesNotMatch(source, /className="review-decision-card"/);
  assert.doesNotMatch(source, /원문과 번역이 자연스러운지 확인하세요/);
  assert.match(css, /\.review-comparison-shell\s*{[^}]*align-content: start;/);
  assert.match(css, /\.review-decision-actions\s*{[^}]*flex-wrap: wrap;/);
});

test("review workspace opens the term registration form only from the term action", () => {
  const source = readFileSync(reviewWorkspacePath, "utf8");

  assert.match(source, /const \[quickAddOpen, setQuickAddOpen\] = useState\(false\)/);
  assert.match(source, /setQuickAddOpen\(true\)/);
  assert.match(source, /quickAddOpen \? \([\s\S]*aria-label="용어 등록"/);
  assert.match(source, /용어 등록 닫기/);
});

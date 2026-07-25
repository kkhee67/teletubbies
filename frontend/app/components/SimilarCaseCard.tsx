"use client";

import { useState } from "react";
import type {
  AiApiStatus,
  SimilarCaseFactorViewModel,
  SimilarCaseViewModel,
} from "../integration";
import "./similar-case.css";
import "./similar-case-live.css";

type SimilarCaseCardProps = {
  cases: SimilarCaseViewModel[];
  generatedAt: string | null;
  aiApiStatus: AiApiStatus;
  aiApiMessage: string | null;
};

function aiStatusNotice(
  status: AiApiStatus,
  apiMessage: string | null,
) {
  if (status === "ok") return null;

  if (status === "local_mock") {
    return {
      tone: "demo",
      title: "현재 모의 유사사례를 표시하고 있습니다",
      message:
        apiMessage ??
        "실제 AI 서비스 대신 백엔드의 로컬 모의사례가 반환되었습니다. 발표용 예시로만 확인해 주세요.",
    };
  }

  if (status === "disabled") {
    return {
      tone: "neutral",
      title: "AI 유사사례 기능이 비활성화되어 있습니다",
      message:
        apiMessage ??
        "매물정보·반환보증·위험 분석 결과는 정상적으로 확인할 수 있습니다.",
    };
  }

  const titles: Record<string, string> = {
    fallback: "AI가 제한된 대체 결과를 반환했습니다",
    unavailable: "AI 유사사례 서비스에 현재 연결되지 않았습니다",
    timeout: "AI 유사사례 응답 시간이 초과되었습니다",
    error: "AI 유사사례 분석 중 오류가 발생했습니다",
    unsupported_product_type: "현재 보증상품은 AI 유사사례를 지원하지 않습니다",
    unknown: "AI 유사사례 연결 상태를 확인할 수 없습니다",
  };

  return {
    tone: status === "unknown" ? "neutral" : "warning",
    title: titles[status] ?? titles.unknown,
    message: [
      apiMessage,
      "핵심 매물정보·반환보증·위험 분석은 백엔드 규칙 분석 결과로 계속 표시됩니다.",
    ]
      .filter(Boolean)
      .join(" "),
  };
}

function caseTitle(item: SimilarCaseViewModel, index: number) {
  return (
    item.title ??
    (item.tags.length > 0 ? item.tags.slice(0, 2).join(" · ") : null) ??
    `유사 상담사례 ${index + 1}`
  );
}

function caseCategory(item: SimilarCaseViewModel) {
  return item.category ?? (item.tags.join(" · ") || "분류 정보 없음");
}

function comparisonItems(item: SimilarCaseViewModel) {
  if (item.factors.length > 0) return item.factors;

  const tags: SimilarCaseFactorViewModel[] = item.tags.map((tag) => ({
    label: tag,
    description: "분석 API가 이 사례의 관련 태그로 반환한 항목입니다.",
    kind: "match",
  }));
  const missedChecks: SimilarCaseFactorViewModel[] = item.missedChecks.map(
    (check) => ({
      label: check,
      description:
        "유사사례에서 놓친 확인 항목으로 API가 반환했습니다. 현재 계약에서도 직접 확인하세요.",
      kind: "unknown",
    }),
  );

  return [...tags, ...missedChecks];
}

function formatDate(value: string | null) {
  if (!value) return "응답 시각 없음";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("ko-KR", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

export function SimilarCaseCard({
  cases,
  generatedAt,
  aiApiStatus,
  aiApiMessage,
}: SimilarCaseCardProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const selectedCase = cases[selectedIndex] ?? cases[0] ?? null;
  const statusNotice = aiStatusNotice(aiApiStatus, aiApiMessage);

  return (
    <section
      className="similar-case-section"
      id="similar-cases"
      aria-labelledby="similar-case-title"
    >
      <div className="similar-case-container">
        <div className="similar-case-heading">
          <div>
            <p className="eyebrow">STEP 05 · 유사사례 설명</p>
            <h2 id="similar-case-title">
              AI 연결 상태와 유사사례 결과를 함께 확인합니다
            </h2>
          </div>
          <p>
            유사도는 문장과 위험 맥락의 가까움을 나타내는 참고값입니다.
            사고확률이나 같은 피해의 예측값이 아닙니다.
          </p>
        </div>

        {statusNotice ? (
          <div
            className={`ai-status-notice ai-status-notice--${statusNotice.tone}`}
            role="status"
          >
            <span aria-hidden="true">AI</span>
            <div>
              <strong>{statusNotice.title}</strong>
              <p>{statusNotice.message}</p>
            </div>
          </div>
        ) : null}

        {selectedCase ? (
          <div className="similar-case-layout">
            <nav className="case-selector" aria-label="유사 상담사례 선택">
              <span>
                {aiApiStatus === "local_mock" ? "모의" : "AI"} 유사사례{" "}
                {cases.length}건
              </span>
              {cases.map((item, index) => {
                const isSelected = index === selectedIndex;

                return (
                  <button
                    type="button"
                    className={isSelected ? "is-selected" : ""}
                    aria-pressed={isSelected}
                    onClick={() => setSelectedIndex(index)}
                    key={`${item.id ?? "case"}:${index}`}
                  >
                    <small>사례 {String(index + 1).padStart(2, "0")}</small>
                    <strong>{caseTitle(item, index)}</strong>
                    <span>{caseCategory(item)}</span>
                    <b>
                      {item.similarity === null
                        ? "유사도 미제공"
                        : `${item.similarity}% 유사`}
                    </b>
                  </button>
                );
              })}
            </nav>

            <article className="case-detail">
              <header className="case-detail-header">
                <div>
                  <span className="ai-label">
                    {aiApiStatus === "local_mock"
                      ? "로컬 모의 유사사례"
                      : "AI 분석 유사사례"}
                  </span>
                  <p>{caseCategory(selectedCase)}</p>
                  <h3>{caseTitle(selectedCase, selectedIndex)}</h3>
                </div>
                <div
                  className="similarity-score"
                  aria-label={
                    selectedCase.similarity === null
                      ? "문장과 위험맥락 유사도 미제공"
                      : `문장과 위험맥락 유사도 ${selectedCase.similarity}%`
                  }
                >
                  <span>문장·위험맥락 유사도</span>
                  <strong>
                    {selectedCase.similarity ?? "—"}
                    <small>%</small>
                  </strong>
                </div>
              </header>

              <section
                className="case-summary"
                aria-labelledby="case-summary-title"
              >
                <span id="case-summary-title">사례 요약</span>
                <p>
                  {selectedCase.summary ??
                    "API 응답에 이 사례의 요약이 없습니다."}
                </p>
              </section>

              <section
                className="match-factor-section"
                aria-labelledby="match-factor-title"
              >
                <div className="section-mini-heading">
                  <span>API 비교 정보</span>
                  <h4 id="match-factor-title">관련 태그와 놓친 확인 항목</h4>
                </div>
                {comparisonItems(selectedCase).length > 0 ? (
                  <ul>
                    {comparisonItems(selectedCase).map((factor, index) => (
                      <li
                        className={`factor--${factor.kind}`}
                        key={`${factor.label ?? "factor"}:${index}`}
                      >
                        <span aria-hidden="true">
                          {factor.kind === "match"
                            ? "✓"
                            : factor.kind === "difference"
                              ? "≠"
                              : "!"}
                        </span>
                        <div>
                          <strong>{factor.label ?? "항목명 없음"}</strong>
                          <p>
                            {factor.description ??
                              "API 응답에 설명이 없습니다."}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="case-inline-empty">
                    API 응답에 비교 근거, 태그 또는 놓친 확인 항목이 없습니다.
                  </p>
                )}
              </section>

              <section
                className="plain-explanation"
                aria-labelledby="plain-explanation-title"
              >
                <div className="plain-explanation-mark" aria-hidden="true">
                  AI
                </div>
                <div>
                  <span>쉽게 풀어쓴 API 설명</span>
                  <h4 id="plain-explanation-title">이 사례의 핵심 의미</h4>
                  <p>
                    {selectedCase.plainExplanation ??
                      "이 사례에는 별도의 쉬운 설명이 제공되지 않았습니다."}
                  </p>
                </div>
              </section>

              <div className="case-metadata">
                <div>
                  <span>사례 식별값</span>
                  <code>{selectedCase.id ?? "not_provided"}</code>
                </div>
                <div>
                  <span>데이터 출처</span>
                  <strong>
                    {selectedCase.sourceName ?? "API 응답에 출처 없음"}
                  </strong>
                </div>
                <div>
                  <span>기준일·분석시각</span>
                  <strong>
                    {formatDate(selectedCase.referenceDate ?? generatedAt)}
                  </strong>
                </div>
              </div>
            </article>
          </div>
        ) : (
          <div className="case-empty-state" role="status">
            <span aria-hidden="true">i</span>
            <div>
              <h3>
                {aiApiStatus === "ok"
                  ? "AI가 반환한 유사사례가 없습니다"
                  : "AI 유사사례 결과를 표시할 수 없습니다"}
              </h3>
              <p>
                화면에서 임의의 사례를 채우지 않습니다. 위의 연결 상태를
                확인하고, 다른 분석 결과와 행동 체크리스트를 이용해 주세요.
              </p>
            </div>
          </div>
        )}

        <div className="case-disclaimer">
          <strong>유사사례는 결과를 예측하지 않습니다.</strong>
          <p>
            현재 계약과 일부 조건이 비슷한 상담을 찾은 참고정보입니다. 같은
            분쟁이나 피해가 발생한다고 단정할 수 없으며, 실제 판단에는 최신
            공식 서류 확인이 필요합니다.
          </p>
        </div>
      </div>
    </section>
  );
}

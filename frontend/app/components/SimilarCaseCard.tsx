"use client";

import { useState } from "react";
import type { GuaranteeStatus } from "../data/guaranteeStates";
import { buildSimilarCasesSample } from "../data/similarCasesSample";
import "./similar-case.css";

type SimilarCaseCardProps = {
  guaranteeStatus: GuaranteeStatus;
};

export function SimilarCaseCard({
  guaranteeStatus,
}: SimilarCaseCardProps) {
  const cases = buildSimilarCasesSample(guaranteeStatus);
  const [selectedCaseId, setSelectedCaseId] = useState(cases[0].id);
  const selectedCase =
    cases.find((item) => item.id === selectedCaseId) ?? cases[0];

  return (
    <section
      className="similar-case-section"
      id="similar-cases"
      aria-labelledby="similar-case-title"
    >
      <div className="similar-case-container">
        <div className="similar-case-heading">
          <div>
            <p className="eyebrow">STEP 05 · AI 사례 설명</p>
            <h2 id="similar-case-title">
              비슷한 상담사례를 쉬운 말로 설명합니다
            </h2>
          </div>
          <p>
            상담문장의 의미와 확인된 위험맥락을 함께 비교합니다. 유사도는
            사고확률이나 같은 피해의 예측값이 아닙니다.
          </p>
        </div>

        <div className="similar-case-layout">
          <nav className="case-selector" aria-label="유사 상담사례 선택">
            <span>유사사례 {cases.length}건</span>
            {cases.map((item, index) => {
              const isSelected = item.id === selectedCase.id;

              return (
                <button
                  type="button"
                  className={isSelected ? "is-selected" : ""}
                  aria-pressed={isSelected}
                  onClick={() => setSelectedCaseId(item.id)}
                  key={item.id}
                >
                  <small>사례 {String(index + 1).padStart(2, "0")}</small>
                  <strong>{item.title}</strong>
                  <span>{item.category}</span>
                  <b>{item.similarity}% 유사</b>
                </button>
              );
            })}
          </nav>

          <article className="case-detail">
            <header className="case-detail-header">
              <div>
                <span className="ai-label">AI 유사사례 · 개발용 샘플</span>
                <p>{selectedCase.category}</p>
                <h3>{selectedCase.title}</h3>
              </div>
              <div
                className="similarity-score"
                aria-label={`문장과 위험맥락 유사도 ${selectedCase.similarity}%`}
              >
                <span>문장·위험맥락 유사도</span>
                <strong>
                  {selectedCase.similarity}
                  <small>%</small>
                </strong>
              </div>
            </header>

            <section className="case-summary" aria-labelledby="case-summary-title">
              <span id="case-summary-title">사례 요약</span>
              <p>{selectedCase.summary}</p>
            </section>

            <section
              className="match-factor-section"
              aria-labelledby="match-factor-title"
            >
              <div className="section-mini-heading">
                <span>비교 근거</span>
                <h4 id="match-factor-title">현재 계약과 닮은 점·다른 점</h4>
              </div>
              <ul>
                {selectedCase.factors.map((factor) => (
                  <li className={`factor--${factor.kind}`} key={factor.label}>
                    <span aria-hidden="true">
                      {factor.kind === "match" ? "✓" : "≠"}
                    </span>
                    <div>
                      <strong>{factor.label}</strong>
                      <p>{factor.description}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            <section
              className="plain-explanation"
              aria-labelledby="plain-explanation-title"
            >
              <div className="plain-explanation-mark" aria-hidden="true">
                AI
              </div>
              <div>
                <span>고등학생도 이해하기 쉬운 설명</span>
                <h4 id="plain-explanation-title">이 사례의 핵심 의미</h4>
                <p>{selectedCase.plainExplanation}</p>
              </div>
            </section>

            <div className="case-metadata">
              <div>
                <span>사례 식별값</span>
                <code>{selectedCase.id}</code>
              </div>
              <div>
                <span>데이터 출처</span>
                <strong>{selectedCase.sourceName}</strong>
              </div>
              <div>
                <span>기준일</span>
                <strong>{selectedCase.referenceDate}</strong>
              </div>
            </div>
          </article>
        </div>

        <div className="case-disclaimer">
          <strong>유사사례는 결과를 예측하지 않습니다.</strong>
          <p>
            현재 계약과 위험조건의 구조가 비슷한 상담을 찾은 참고정보입니다.
            같은 분쟁이나 피해가 발생한다고 단정할 수 없으며, 실제 판단에는
            최신 공식 서류 확인이 필요합니다.
          </p>
        </div>
      </div>
    </section>
  );
}

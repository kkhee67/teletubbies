"use client";

import "./guarantee-status.css";
import {
  guaranteeGroupLabels,
  guaranteeGroupOrder,
  guaranteeStates,
  type GuaranteeStatus,
} from "../data/guaranteeStates";

type GuaranteeStatusCardProps = {
  selectedStatus: GuaranteeStatus;
  onStatusChange: (status: GuaranteeStatus) => void;
};

const statusOptions: GuaranteeStatus[] = [
  "estimated_eligible",
  "officially_eligible",
  "applied",
  "enrolled",
  "ineligible",
  "unknown",
];

export function GuaranteeStatusCard({
  selectedStatus,
  onStatusChange,
}: GuaranteeStatusCardProps) {
  const state = guaranteeStates[selectedStatus];
  const isEnrolled = selectedStatus === "enrolled";

  return (
    <section
      className={`guarantee-section guarantee-section--${state.group}`}
      id="guarantee-status"
      aria-labelledby="guarantee-title"
    >
      <div className="guarantee-container">
        <div className="guarantee-heading">
          <div>
            <p className="eyebrow">STEP 03 · 반환보증 상태</p>
            <h2 id="guarantee-title">가입 가능과 가입 완료를 구분합니다</h2>
            <p>
              반환보증 내부 상태 6개를 사용자가 이해하기 쉬운 4개 화면
              그룹으로 나누어 안내합니다.
            </p>
          </div>

          <label className="status-demo-control" htmlFor="guarantee-demo-status">
            <span>API 연동 전 상태 시연</span>
            <select
              id="guarantee-demo-status"
              value={selectedStatus}
              onChange={(event) =>
                onStatusChange(event.target.value as GuaranteeStatus)
              }
            >
              {statusOptions.map((status) => (
                <option value={status} key={status}>
                  {guaranteeStates[status].statusLabel}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="guarantee-stage-list" aria-label="반환보증 화면 그룹">
          {guaranteeGroupOrder.map((group, index) => (
            <div
              className={group === state.group ? "is-active" : ""}
              key={group}
              aria-current={group === state.group ? "step" : undefined}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{guaranteeGroupLabels[group]}</strong>
            </div>
          ))}
        </div>

        <article className="guarantee-main-card">
          <div className="guarantee-status-copy">
            <span className="guarantee-group-badge">{state.groupTitle}</span>
            <p>현재 반환보증 상태</p>
            <h3>{state.displayText}</h3>
            <div className="guarantee-message">{state.message}</div>

            <div
              className={`completion-notice ${
                isEnrolled ? "is-complete" : "is-not-complete"
              }`}
            >
              <span aria-hidden="true">{isEnrolled ? "✓" : "!"}</span>
              <div>
                <strong>
                  {isEnrolled
                    ? "보호장치 확보가 확인되었습니다."
                    : "현재 상태는 가입 완료가 아닙니다."}
                </strong>
                <p>
                  {isEnrolled
                    ? "보증 가입 외에도 근저당과 다른 권리관계를 계속 확인하세요."
                    : "가입 가능, 사전확인, 신청 중 상태를 실제 가입 완료와 혼동하지 마세요."}
                </p>
              </div>
            </div>
          </div>

          <aside className="guarantee-actions">
            <span>지금 확인할 일</span>
            <ol>
              {state.nextActions.map((action) => (
                <li key={action}>{action}</li>
              ))}
            </ol>
          </aside>
        </article>

        <div className="guarantee-metadata">
          <div>
            <span>내부 상태값</span>
            <code>{state.status}</code>
          </div>
          <div>
            <span>데이터 출처</span>
            <strong>반환보증 API 연동 전 샘플</strong>
          </div>
          <div>
            <span>기준일</span>
            <strong>2026-07-25</strong>
          </div>
        </div>

        <p className="guarantee-disclaimer">
          반환보증 상태는 계약의 전체 안전도를 의미하지 않습니다. 실제
          서비스에서는 공식 확인 결과와 최신 기준일을 함께 표시합니다.
        </p>
      </div>
    </section>
  );
}

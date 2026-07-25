import type {
  GuaranteeGroup,
  GuaranteeStatus,
  GuaranteeViewModel,
} from "../integration";
import "./guarantee-status.css";

type GuaranteeStatusCardProps = {
  guarantee: GuaranteeViewModel;
  generatedAt: string | null;
};

const guaranteeGroupOrder: GuaranteeGroup[] = [
  "check_required",
  "in_progress",
  "protected",
  "deep_analysis",
];

const guaranteeGroupLabels: Record<GuaranteeGroup, string> = {
  check_required: "확인 필요",
  in_progress: "가입 절차 진행",
  protected: "보호장치 확보",
  deep_analysis: "심층분석 필요",
};

const statusPresentation: Record<
  GuaranteeStatus,
  { group: GuaranteeGroup; displayText: string }
> = {
  estimated_eligible: {
    group: "check_required",
    displayText: "가입 가능성 확인",
  },
  officially_eligible: {
    group: "in_progress",
    displayText: "공식 사전확인 완료",
  },
  applied: {
    group: "in_progress",
    displayText: "가입 신청 중",
  },
  enrolled: {
    group: "protected",
    displayText: "반환보증 가입 완료",
  },
  ineligible: {
    group: "deep_analysis",
    displayText: "가입 어려움",
  },
  unknown: {
    group: "check_required",
    displayText: "반환보증 상태 미확인",
  },
};

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

export function GuaranteeStatusCard({
  guarantee,
  generatedAt,
}: GuaranteeStatusCardProps) {
  const status = guarantee.status ?? "unknown";
  const presentation = statusPresentation[status];
  const group = guarantee.group ?? presentation.group;
  const isEnrolled = status === "enrolled";
  const displayText = guarantee.displayText ?? presentation.displayText;

  return (
    <section
      className={`guarantee-section guarantee-section--${group}`}
      id="guarantee-status"
      aria-labelledby="guarantee-title"
    >
      <div className="guarantee-container">
        <div className="guarantee-heading">
          <div>
            <p className="eyebrow">STEP 03 · 반환보증 상태</p>
            <h2 id="guarantee-title">
              가입 가능성과 가입 완료를 구분합니다
            </h2>
            <p>
              분석 API의 보증 분기와 메시지를 표시합니다. ‘가입 가능’ 응답은
              실제 가입 완료나 보증서 발급으로 해석하지 않습니다.
            </p>
          </div>
        </div>

        <div className="guarantee-stage-list" aria-label="반환보증 화면 그룹">
          {guaranteeGroupOrder.map((item, index) => (
            <div
              className={item === group ? "is-active" : ""}
              key={item}
              aria-current={item === group ? "step" : undefined}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{guaranteeGroupLabels[item]}</strong>
            </div>
          ))}
        </div>

        <article className="guarantee-main-card">
          <div className="guarantee-status-copy">
            <span className="guarantee-group-badge">
              {guaranteeGroupLabels[group]}
            </span>
            <p>현재 반환보증 상태</p>
            <h3>{displayText}</h3>
            <div className="guarantee-message">
              {guarantee.message ??
                "분석 API 응답에 반환보증 설명이 없습니다."}
            </div>

            <div
              className={`completion-notice ${
                isEnrolled ? "is-complete" : "is-not-complete"
              }`}
            >
              <span aria-hidden="true">{isEnrolled ? "✓" : "!"}</span>
              <div>
                <strong>
                  {isEnrolled
                    ? "가입 완료 상태가 API 응답에서 확인되었습니다."
                    : "가입 완료로 확인된 상태가 아닙니다."}
                </strong>
                <p>
                  {isEnrolled
                    ? "보증서와 보증기간을 확인하고 다른 권리관계도 계속 점검하세요."
                    : "공식 사전확인, 신청 또는 가능성 응답을 실제 가입 완료와 혼동하지 마세요."}
                </p>
              </div>
            </div>
          </div>

          <aside className="guarantee-actions">
            <span>API가 제공한 다음 행동</span>
            {guarantee.nextActions.length > 0 ? (
              <ol>
                {guarantee.nextActions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ol>
            ) : (
              <p className="guarantee-actions-empty">
                이 응답에는 보증 전용 행동 목록이 없습니다. 아래의 분석
                체크리스트와 권장 행동을 확인하세요.
              </p>
            )}
          </aside>
        </article>

        <div className="guarantee-metadata">
          <div>
            <span>보증 분석 분기</span>
            <code>{guarantee.branch ?? "not_provided"}</code>
          </div>
          <div>
            <span>매물 보증 상태</span>
            <code>{guarantee.propertyStatus ?? "not_provided"}</code>
          </div>
          <div>
            <span>데이터 출처</span>
            <strong>POST /analyze 응답</strong>
          </div>
          <div>
            <span>분석 시각</span>
            <strong>{formatDate(generatedAt)}</strong>
          </div>
        </div>

        <p className="guarantee-disclaimer">
          {guarantee.disclaimer ??
            "반환보증 상태는 계약의 전체 안전을 의미하지 않습니다. 공식 기관의 최신 결과를 다시 확인해야 합니다."}
        </p>
      </div>
    </section>
  );
}

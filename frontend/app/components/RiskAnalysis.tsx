import type {
  RiskAnalysisViewModel,
  RiskSeverity,
  RiskSignalViewModel,
} from "../integration";
import "./risk-analysis.css";
import "./risk-analysis-live.css";

type RiskAnalysisProps = {
  analysis: RiskAnalysisViewModel;
};

type StageTone = "basic" | "check" | "caution" | "review";

const riskStages: Array<{ tone: StageTone; label: string }> = [
  { tone: "basic", label: "기본 확인" },
  { tone: "check", label: "확인 필요" },
  { tone: "caution", label: "주의" },
  { tone: "review", label: "계약 전 재검토" },
];

const stageDescriptions: Record<StageTone, string> = {
  basic:
    "현재 확인된 위험은 없지만 계약이 안전하다는 뜻은 아닙니다. 최신 공식 서류와 남은 확인 항목을 계약 전에 검토하세요.",
  check:
    "미확인 정보나 추가 확인 항목이 있습니다. 체크리스트를 완료한 뒤 같은 조건으로 다시 분석하는 것이 좋습니다.",
  caution:
    "확인된 위험신호가 있어 보증금과 권리관계, 반환보증 조건을 계약 전에 자세히 확인해야 합니다.",
  review:
    "강한 위험신호가 확인된 구간입니다. 즉시 진행하기보다 핵심 서류와 계약 조건을 먼저 재검토하세요.",
};

const severityLabels: Record<RiskSeverity, string> = {
  critical: "매우 높음",
  high: "높음",
  medium: "중간",
  low: "낮음",
  check: "확인 필요",
  unknown: "미분류",
};

function stageTone(stage: string | null): StageTone {
  if (!stage) return "check";
  if (/재검토|매우.?높|critical/i.test(stage)) return "review";
  if (/주의|높음|high/i.test(stage)) return "caution";
  if (/확인|check|unknown/i.test(stage)) return "check";
  return "basic";
}

function severityClass(severity: RiskSeverity) {
  if (severity === "critical" || severity === "high") return "high";
  if (severity === "medium" || severity === "low") return "medium";
  return "check";
}

function signalKey(signal: RiskSignalViewModel, index: number) {
  return `${signal.code ?? signal.title ?? "signal"}:${index}`;
}

function SignalList({
  signals,
  emptyMessage,
}: {
  signals: RiskSignalViewModel[];
  emptyMessage: string;
}) {
  if (signals.length === 0) {
    return <p className="result-items-empty">{emptyMessage}</p>;
  }

  return (
    <div className="result-items">
      {signals.map((signal, index) => (
        <article key={signalKey(signal, index)}>
          <div>
            <span
              className={`severity-badge severity-badge--${severityClass(
                signal.severity,
              )}`}
            >
              {severityLabels[signal.severity]}
            </span>
            <code>{signal.code ?? "CODE_NOT_PROVIDED"}</code>
          </div>
          <h4>{signal.title ?? "제목이 제공되지 않은 신호"}</h4>
          <p>
            {signal.description ??
              "API 응답에 이 신호의 설명이 제공되지 않았습니다."}
          </p>
          {signal.action || signal.basis ? (
            <small>
              {signal.action
                ? `확인 행동 · ${signal.action}`
                : `판단 근거 · ${signal.basis}`}
            </small>
          ) : null}
        </article>
      ))}
    </div>
  );
}

export function RiskAnalysis({ analysis }: RiskAnalysisProps) {
  const tone = stageTone(analysis.riskStage);
  return (
    <section
      className={`analysis-section analysis-section--${tone}`}
      id="risk-analysis"
      aria-labelledby="analysis-title"
    >
      <div className="analysis-container">
        <div className="analysis-heading">
          <p className="eyebrow">STEP 04 · 분석 결과</p>
          <h2 id="analysis-title">
            확정 위험과 확인 필요 정보를 따로 보여드립니다
          </h2>
          <p>
            위험단계를 유지하면서 확인된 사실과 아직 확인되지 않은 정보를
            구분합니다.
          </p>
        </div>

        <div className="stage-scale" aria-label="위험단계">
          {riskStages.map((stage) => (
            <div
              className={stage.tone === tone ? "is-current" : ""}
              aria-current={stage.tone === tone ? "step" : undefined}
              key={stage.tone}
            >
              <span />
              <strong>{stage.label}</strong>
            </div>
          ))}
        </div>

        <div className="analysis-overview">
          <article className="stage-card">
            <span>현재 위험단계</span>
            <h3>{analysis.riskStage ?? "응답 없음"}</h3>
            <p>{stageDescriptions[tone]}</p>
            <small>
              위험단계는 위험신호를 정리한 참고 구간이며 계약 안전을 보장하지
              않습니다.
            </small>
          </article>

          <div className="analysis-stats">
            <article className="analysis-stat analysis-stat--risk">
              <span>확정 위험</span>
              <strong>
                {analysis.confirmedRisks.length}
                <small>개</small>
              </strong>
              <p>자료에서 위험요인으로 확인된 사실</p>
            </article>
            <article className="analysis-stat analysis-stat--check">
              <span>확인 필요</span>
              <strong>
                {analysis.requiredChecks.length}
                <small>개</small>
              </strong>
              <p>자료가 없거나 추가 확인이 필요한 항목</p>
            </article>
          </div>
        </div>

        <div className="analysis-lists">
          <section
            className="confirmed-risk-panel"
            aria-labelledby="confirmed-title"
          >
            <div className="list-panel-heading">
              <div>
                <span>확인된 사실</span>
                <h3 id="confirmed-title">확정 위험</h3>
              </div>
              <strong>{analysis.confirmedRisks.length}</strong>
            </div>
            <SignalList
              signals={analysis.confirmedRisks}
              emptyMessage="API 응답에 확정 위험이 없습니다. 이것만으로 계약이 안전하다는 뜻은 아닙니다."
            />
          </section>

          <section
            className="required-check-panel"
            aria-labelledby="required-title"
          >
            <div className="list-panel-heading">
              <div>
                <span>아직 모르는 정보</span>
                <h3 id="required-title">확인 필요</h3>
              </div>
              <strong>{analysis.requiredChecks.length}</strong>
            </div>
            <SignalList
              signals={analysis.requiredChecks}
              emptyMessage="API 응답에 별도의 미확인 신호가 없습니다."
            />
          </section>

          {analysis.referenceSignals.length > 0 ? (
            <section
              className="reference-signal-panel"
              aria-labelledby="reference-signal-title"
            >
              <div className="list-panel-heading">
                <div>
                  <span>위험단계와 별도로 보는 정보</span>
                  <h3 id="reference-signal-title">참고 신호</h3>
                </div>
                <strong>{analysis.referenceSignals.length}</strong>
              </div>
              <SignalList
                signals={analysis.referenceSignals}
                emptyMessage="API 응답에 별도의 참고 신호가 없습니다."
              />
              <p className="reference-signal-note">
                이 항목은 확정 위험이나 확인 필요로 분류되지 않았지만 분석
                API가 함께 반환한 참고 정보입니다.
              </p>
            </section>
          ) : null}
        </div>

        <article className="analysis-recommendation">
          <div>
            <span>분석 API 권장 행동</span>
            <h3>
              {analysis.recommendedAction?.label ??
                "별도 권장 행동이 제공되지 않았습니다"}
            </h3>
            <p>
              {analysis.recommendedAction?.description ??
                "아래 행동 체크리스트에서 API가 반환한 확인 항목을 검토하세요."}
            </p>
          </div>
          <strong>{analysis.checklist.length}개 체크 항목</strong>
        </article>

        <div className="analysis-notice">
          <strong>결과 해석 안내</strong>
          <p>
            {analysis.notice ??
              "위험단계는 계약 전 의사결정을 돕는 참고 신호입니다."}{" "}
            {analysis.disclaimer ??
              "실제 계약 전에는 최신 공식 서류와 전문가 확인이 필요합니다."}
          </p>
        </div>
      </div>
    </section>
  );
}

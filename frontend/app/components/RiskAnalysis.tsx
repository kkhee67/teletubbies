import "./risk-analysis.css";
import { buildAnalysisSample, type RiskStage } from "../data/analysisSample";
import type { GuaranteeStatus } from "../data/guaranteeStates";

type RiskAnalysisProps = {
  guaranteeStatus: GuaranteeStatus;
};

const riskStages: RiskStage[] = [
  "기본 확인",
  "추가 확인 필요",
  "주의",
  "계약 전 재검토",
];

const stageDescriptions: Record<RiskStage, string> = {
  "기본 확인":
    "현재 확인된 자료에서 강한 위험신호가 발견되지 않았지만 공식 서류 확인은 계속 필요합니다.",
  "추가 확인 필요":
    "확정되지 않은 핵심 정보가 있어 계약 전에 추가 확인이 필요합니다.",
  주의: "확인된 위험신호가 있어 계약조건과 공식 서류를 주의 깊게 검토해야 합니다.",
  "계약 전 재검토":
    "강한 위험신호가 여러 개 확인되어 현재 조건으로 계약하기 전에 재검토가 필요합니다.",
};

const stageClassNames: Record<RiskStage, string> = {
  "기본 확인": "basic",
  "추가 확인 필요": "check",
  주의: "caution",
  "계약 전 재검토": "review",
};

export function RiskAnalysis({ guaranteeStatus }: RiskAnalysisProps) {
  const analysis = buildAnalysisSample(guaranteeStatus);
  const stageClassName = stageClassNames[analysis.riskStage];

  return (
    <section
      className={`analysis-section analysis-section--${stageClassName}`}
      id="risk-analysis"
      aria-labelledby="analysis-title"
    >
      <div className="analysis-container">
        <div className="analysis-heading">
          <p className="eyebrow">STEP 04 · 분석 결과</p>
          <h2 id="analysis-title">위험과 미확인 정보를 따로 보여드립니다</h2>
          <p>
            확인된 사실만 위험신호로 표시하고, 아직 모르는 정보는 별도의
            확인 목록으로 분리합니다.
          </p>
        </div>

        <div className="stage-scale" aria-label="위험단계">
          {riskStages.map((stage) => (
            <div
              className={stage === analysis.riskStage ? "is-current" : ""}
              aria-current={stage === analysis.riskStage ? "step" : undefined}
              key={stage}
            >
              <span />
              <strong>{stage}</strong>
            </div>
          ))}
        </div>

        <div className="analysis-overview">
          <article className="stage-card">
            <span>현재 위험단계</span>
            <h3>{analysis.riskStage}</h3>
            <p>{stageDescriptions[analysis.riskStage]}</p>
            <small>위험단계는 사고확률이나 법률적 확정판단이 아닙니다.</small>
          </article>

          <div className="analysis-stats">
            <article className="analysis-stat analysis-stat--risk">
              <span>확인된 위험신호</span>
              <strong>{analysis.confirmedRisks.length}<small>개</small></strong>
              <p>자료에서 실제로 확인된 조건</p>
            </article>
            <article className="analysis-stat analysis-stat--check">
              <span>확인이 필요한 정보</span>
              <strong>{analysis.requiredChecks.length}<small>개</small></strong>
              <p>아직 확인되지 않은 필수 항목</p>
            </article>
            <article className="analysis-stat analysis-stat--confidence">
              <span>분석 신뢰도</span>
              <strong>{analysis.analysisConfidence}<small>%</small></strong>
              <p>안전도가 아닌 정보 확인 정도</p>
            </article>
          </div>
        </div>

        <div className="analysis-lists">
          <section className="confirmed-risk-panel" aria-labelledby="confirmed-title">
            <div className="list-panel-heading">
              <div>
                <span>확인된 사실</span>
                <h3 id="confirmed-title">확인된 위험신호</h3>
              </div>
              <strong>{analysis.confirmedRisks.length}</strong>
            </div>
            <div className="result-items">
              {analysis.confirmedRisks.map((risk) => (
                <article key={risk.code}>
                  <div>
                    <span className={`severity-badge severity-badge--${risk.severity}`}>
                      {risk.severity === "high" ? "높음" : "주의"}
                    </span>
                    <code>{risk.code}</code>
                  </div>
                  <h4>{risk.title}</h4>
                  <p>{risk.description}</p>
                  <small>근거 · {risk.basis}</small>
                </article>
              ))}
            </div>
          </section>

          <section className="required-check-panel" aria-labelledby="checks-title">
            <div className="list-panel-heading">
              <div>
                <span>미확인 정보</span>
                <h3 id="checks-title">확인이 필요한 정보</h3>
              </div>
              <strong>{analysis.requiredChecks.length}</strong>
            </div>
            <div className="result-items">
              {analysis.requiredChecks.map((item) => (
                <article key={item.code}>
                  <div>
                    <span className="severity-badge severity-badge--check">
                      확인 필요
                    </span>
                    <code>{item.code}</code>
                  </div>
                  <h4>{item.title}</h4>
                  <p>{item.description}</p>
                  <small>다음 행동 · {item.action}</small>
                </article>
              ))}
            </div>
          </section>
        </div>

        <article className="confidence-card">
          <div className="confidence-copy">
            <span>분석 신뢰도</span>
            <strong>{analysis.analysisConfidence}%</strong>
          </div>
          <div className="confidence-detail">
            <div
              className="confidence-track"
              role="progressbar"
              aria-label="분석에 필요한 정보 확인 정도"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={analysis.analysisConfidence}
            >
              <span style={{ width: `${analysis.analysisConfidence}%` }} />
            </div>
            <p>
              분석에 필요한 정보 중 공식자료 또는 사용자 확인으로 채워진
              정도입니다. <strong>계약의 안전도를 의미하지 않습니다.</strong>
            </p>
          </div>
        </article>

        <div className="analysis-notice">
          <strong>“기본 확인”도 안전하다는 뜻은 아닙니다.</strong>
          <p>
            강한 위험신호가 발견되지 않았다는 의미일 뿐이며, 실제 계약에서는
            최신 공식 서류와 반환보증 가입 여부를 다시 확인해야 합니다.
          </p>
        </div>
      </div>
    </section>
  );
}

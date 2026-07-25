import "./property-summary.css";
import { propertySample, type PropertyFieldStatus } from "../data/propertySample";

type PropertySummaryProps = {
  address: string;
  deposit: string;
  onEdit: () => void;
};

const statusLabels: Record<PropertyFieldStatus, string> = {
  neutral: "정보",
  stable: "확인",
  warning: "주의",
  check: "확인 필요",
};

function toDisplayAddress(address: string) {
  const parts = address.trim().split(/\s+/);
  if (parts.length < 2) return address.trim();
  return `${parts.slice(0, -1).join(" ")} 일대`;
}

export function PropertySummary({
  address,
  deposit,
  onEdit,
}: PropertySummaryProps) {
  return (
    <section
      className="property-section"
      id="property-summary"
      aria-labelledby="property-title"
    >
      <div className="property-container">
        <div className="section-heading">
          <div>
            <p className="eyebrow">STEP 02 · 매물정보 확인</p>
            <h2 id="property-title">분석에 사용할 매물정보입니다</h2>
            <p>
              실제 데이터 연결 전에는 화면 구성과 API 응답 형식을 확인할 수
              있도록 샘플값을 표시합니다.
            </p>
          </div>
          <span className="sample-data-badge">API 연결 전 샘플</span>
        </div>

        <div className="property-identity">
          <div>
            <span>표시 주소</span>
            <strong>{toDisplayAddress(address)}</strong>
            <small>상세주소를 제외한 축약 주소</small>
          </div>
          <div>
            <span>계약 예정 보증금</span>
            <strong>{deposit}원</strong>
            <small>사용자 입력</small>
          </div>
        </div>

        <div className="source-guide">
          <span aria-hidden="true">i</span>
          <p>
            매물 전체에 하나의 출처를 붙이지 않고, 주택유형·가액·권리정보
            각각에 출처와 기준일을 표시합니다.
          </p>
        </div>

        <div className="property-grid">
          {propertySample.map((field) => (
            <article
              className={`property-card property-card--${field.status}`}
              key={field.key}
            >
              <div className="property-card-heading">
                <span>{field.label}</span>
                <em>{statusLabels[field.status]}</em>
              </div>
              <strong>{field.value}</strong>
              <p>{field.description}</p>
              <dl>
                <div>
                  <dt>출처</dt>
                  <dd>{field.sourceName}</dd>
                </div>
                <div>
                  <dt>기준일</dt>
                  <dd>{field.referenceDate}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>

        <div className="integration-note">
          <div>
            <strong>실제 데이터 연결 준비</strong>
            <p>
              팀원이 제공하는 주소·매물·권리분석 API 응답으로 샘플 데이터
              파일만 교체하면 같은 화면에 실제 값이 표시됩니다.
            </p>
          </div>
          <button className="secondary-button" type="button" onClick={onEdit}>
            입력 정보 수정
          </button>
        </div>

        <div className="next-step-preview">
          <span>다음 단계</span>
          <strong>반환보증 상태 확인</strong>
          <p>가입 가능성과 실제 가입 완료를 구분해 보여줍니다.</p>
        </div>
      </div>
    </section>
  );
}

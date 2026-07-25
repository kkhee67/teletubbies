import type {
  PropertyFieldViewModel,
  PropertySearchItem,
  PropertySummaryViewModel,
} from "../integration";
import "./property-summary.css";

type PropertySummaryProps = {
  property: PropertySummaryViewModel;
  searchItem: PropertySearchItem;
  searchedAddress: string;
  plannedDeposit: number;
  onEdit: () => void;
};

const statusLabels: Record<PropertyFieldViewModel["status"], string> = {
  neutral: "정보",
  stable: "확인",
  warning: "주의",
  check: "확인 필요",
};

const valueLabels: Record<string, string> = {
  apartment: "아파트",
  detached: "단독주택",
  multi_household: "다가구주택",
  multi_unit: "다세대주택",
  officetel: "오피스텔",
  row_house: "연립주택",
  eligible: "가입 가능성 있음",
  estimated_eligible: "가입 가능성 확인 필요",
  officially_eligible: "공식 가입 가능 확인",
  applied: "가입 신청 중",
  enrolled: "가입 완료",
  ineligible: "가입 어려움",
  exists: "있음",
  none: "확인된 내역 없음",
  promised_removal: "말소 예정",
  removed: "말소 완료",
  unknown: "확인 필요",
};

function formatWon(value: number) {
  return `${new Intl.NumberFormat("ko-KR").format(value)}원`;
}


function formatFieldValue(field: PropertyFieldViewModel) {
  if (field.value === null) return "응답 없음";
  if (field.key === "reference_value" && typeof field.value === "number") {
    return formatWon(field.value);
  }
  if (typeof field.value === "boolean") {
    return field.value ? "예" : "아니요";
  }
  return valueLabels[String(field.value).toLowerCase()] ?? String(field.value);
}

function fieldDescription(
  field: PropertyFieldViewModel,
  property: PropertySummaryViewModel,
) {
  if (field.description) return field.description;
  if (field.value === null) {
    return "분석 응답에 값이 없어 계약 전에 별도 확인이 필요합니다.";
  }
  if (field.key === "reference_value" && property.depositRatio !== null) {
    return `계약 예정 보증금은 이 참고가액의 ${property.depositRatio}%입니다.`;
  }
  if (field.key === "mortgage_status") {
    return "선순위 권리와 실제 말소 여부를 최신 등기부에서 확인하세요.";
  }
  if (field.key === "seizure_status") {
    return "압류·가압류 상태는 최신 공식 서류로 다시 확인해야 합니다.";
  }
  if (field.key === "joint_collateral") {
    return "다른 부동산과 같은 채무의 담보로 묶였는지 확인하세요.";
  }
  return "분석 API의 매물 요약 응답입니다.";
}

export function PropertySummary({
  property,
  searchItem,
  searchedAddress,
  plannedDeposit,
  onEdit,
}: PropertySummaryProps) {
  const displayAddress =
    property.addressDisplay ?? searchItem.addressDisplay ?? searchedAddress;
  const displayDeposit = property.plannedDeposit ?? plannedDeposit;
  const propertyId = property.propertyId ?? searchItem.propertyId;

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
            <h2 id="property-title">분석에 사용한 실제 API 응답입니다</h2>
            <p>
              주소 검색에서 선택한 매물 ID로 분석을 요청했습니다. 값이 없는
              항목은 임의로 채우지 않고 ‘응답 없음’으로 표시합니다.
            </p>
          </div>
          <span className="api-data-badge">LIVE API 응답</span>
        </div>

        <div className="property-identity">
          <div>
            <span>분석 주소</span>
            <strong>{displayAddress}</strong>
            <small>매물 ID · {propertyId}</small>
          </div>
          <div>
            <span>계약 예정 보증금</span>
            <strong>{formatWon(displayDeposit)}</strong>
            <small>사용자 입력값을 분석 요청에 전달</small>
          </div>
        </div>


        <div className="property-grid">
          {property.fields.map((field) => (
            <article
              className={`property-card property-card--${field.status}`}
              key={field.key}
            >
              <div className="property-card-heading">
                <span>{field.label}</span>
                <em>{statusLabels[field.status]}</em>
              </div>
              <strong>{formatFieldValue(field)}</strong>
              <p>{fieldDescription(field, property)}</p>
            </article>
          ))}
        </div>

        <div className="integration-note">
          <div>
            <strong>검색 → 분석 연결 완료</strong>
            <p>
              선택한 검색 결과 <code>{searchItem.propertyId}</code>를 분석
              요청의 <code>property_id</code>로 사용했습니다.
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

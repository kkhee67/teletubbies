export type PropertyFieldStatus = "neutral" | "stable" | "warning" | "check";

export type PropertyField = {
  key: string;
  label: string;
  value: string;
  description: string;
  sourceName: string;
  sourceType: "sample" | "official" | "user_confirmed";
  referenceDate: string;
  status: PropertyFieldStatus;
};

export const propertySample: PropertyField[] = [
  {
    key: "housing_type",
    label: "주택유형",
    value: "다세대주택",
    description: "세대별로 구분등기된 공동주택입니다.",
    sourceName: "매물 데이터 API 연동 전 샘플",
    sourceType: "sample",
    referenceDate: "2026-07-25",
    status: "neutral",
  },
  {
    key: "reference_value",
    label: "참고 주택가액",
    value: "220,000,000원",
    description: "위험분석에 사용할 참고값이며 실제 시세와 다를 수 있습니다.",
    sourceName: "매물 데이터 API 연동 전 샘플",
    sourceType: "sample",
    referenceDate: "2026-07-25",
    status: "neutral",
  },
  {
    key: "mortgage",
    label: "근저당",
    value: "선순위 근저당 있음",
    description: "채권최고액과 계약 전 말소 여부를 추가로 확인해야 합니다.",
    sourceName: "권리분석 API 연동 전 샘플",
    sourceType: "sample",
    referenceDate: "2026-07-25",
    status: "warning",
  },
  {
    key: "seizure",
    label: "압류·가압류",
    value: "확인된 내역 없음",
    description: "실제 분석에서는 최신 공식 서류를 다시 확인합니다.",
    sourceName: "권리분석 API 연동 전 샘플",
    sourceType: "sample",
    referenceDate: "2026-07-25",
    status: "stable",
  },
  {
    key: "joint_collateral",
    label: "공동담보",
    value: "확인 필요",
    description: "다른 부동산과 함께 담보로 설정됐는지 확인이 필요합니다.",
    sourceName: "권리분석 API 연동 전 샘플",
    sourceType: "sample",
    referenceDate: "2026-07-25",
    status: "check",
  },
];

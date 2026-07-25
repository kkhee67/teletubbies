export type GuaranteeStatus =
  | "estimated_eligible"
  | "officially_eligible"
  | "applied"
  | "enrolled"
  | "ineligible"
  | "unknown";

export type GuaranteeGroup =
  | "protected"
  | "in_progress"
  | "deep_analysis"
  | "check_required";

export type GuaranteeState = {
  status: GuaranteeStatus;
  statusLabel: string;
  group: GuaranteeGroup;
  groupTitle: string;
  displayText: string;
  message: string;
  nextActions: string[];
};

export const guaranteeStates: Record<GuaranteeStatus, GuaranteeState> = {
  estimated_eligible: {
    status: "estimated_eligible",
    statusLabel: "내부 추정상 가입 가능",
    group: "check_required",
    groupTitle: "확인 필요",
    displayText: "가입 가능성 있음",
    message:
      "현재 입력 조건으로는 가입 가능성이 있어 보이지만 공식 확인 결과는 아닙니다.",
    nextActions: [
      "공식 사전확인 절차 진행",
      "가입조건과 제한사항 확인",
      "가입 완료 전까지 보호장치로 단정하지 않기",
    ],
  },
  officially_eligible: {
    status: "officially_eligible",
    statusLabel: "공식 가입 가능 확인",
    group: "in_progress",
    groupTitle: "가입 절차 진행",
    displayText: "공식 사전확인 완료",
    message:
      "공식 사전확인 결과 가입 가능한 상태지만 아직 실제 가입이 완료된 것은 아닙니다.",
    nextActions: [
      "보증 신청 절차 시작",
      "필요 서류와 신청기한 확인",
      "최종 가입 완료 여부 확인",
    ],
  },
  applied: {
    status: "applied",
    statusLabel: "가입 신청 완료",
    group: "in_progress",
    groupTitle: "가입 절차 진행",
    displayText: "가입 신청 중",
    message:
      "반환보증을 신청한 상태입니다. 심사 결과와 실제 가입 완료 여부를 확인해야 합니다.",
    nextActions: [
      "심사 진행상태 확인",
      "보완서류 요청 여부 확인",
      "가입 완료 증빙 확인",
    ],
  },
  enrolled: {
    status: "enrolled",
    statusLabel: "실제 가입 완료",
    group: "protected",
    groupTitle: "보호장치 확보",
    displayText: "반환보증 가입 완료",
    message:
      "반환보증 가입 완료가 확인되었습니다. 다른 권리관계도 계속 확인해야 합니다.",
    nextActions: [
      "보증서와 보증기간 보관",
      "계약 변경 시 보증조건 유지 여부 확인",
      "근저당 등 다른 권리관계 계속 점검",
    ],
  },
  ineligible: {
    status: "ineligible",
    statusLabel: "가입이 어렵거나 불가",
    group: "deep_analysis",
    groupTitle: "심층분석 필요",
    displayText: "가입 어려움",
    message:
      "가입이 어려워 추가 위험분석과 계약조건 검토가 필요한 상태입니다.",
    nextActions: [
      "가입 불가 또는 제한 사유 확인",
      "보증금·근저당 등 계약조건 재검토",
      "계약 진행 전 전문가 확인 고려",
    ],
  },
  unknown: {
    status: "unknown",
    statusLabel: "상태 미확인",
    group: "check_required",
    groupTitle: "확인 필요",
    displayText: "반환보증 상태 미확인",
    message:
      "가입 가능성 또는 현재 진행상태를 아직 확정할 수 없습니다.",
    nextActions: [
      "계약 전 가입 가능 여부 확인",
      "주택가액과 선순위채권 정보 준비",
      "확인 전에는 보호장치가 있다고 가정하지 않기",
    ],
  },
};

export const guaranteeGroupOrder: GuaranteeGroup[] = [
  "check_required",
  "in_progress",
  "protected",
  "deep_analysis",
];

export const guaranteeGroupLabels: Record<GuaranteeGroup, string> = {
  check_required: "확인 필요",
  in_progress: "가입 절차 진행",
  protected: "보호장치 확보",
  deep_analysis: "심층분석 필요",
};

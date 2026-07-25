import type { GuaranteeStatus } from "./guaranteeStates";

export type RiskStage =
  | "기본 확인"
  | "추가 확인 필요"
  | "주의"
  | "계약 전 재검토";

export type ConfirmedRisk = {
  code: string;
  title: string;
  severity: "high" | "medium";
  description: string;
  basis: string;
};

export type RequiredCheck = {
  code: string;
  title: string;
  severity: "check";
  description: string;
  action: string;
};

export type AnalysisResult = {
  riskStage: RiskStage;
  confirmedRisks: ConfirmedRisk[];
  requiredChecks: RequiredCheck[];
  analysisConfidence: number;
};

const baseConfirmedRisks: ConfirmedRisk[] = [
  {
    code: "MORTGAGE_EXISTS",
    title: "선순위 근저당 확인",
    severity: "high",
    description:
      "은행 등 선순위 권리자가 경매대금에서 먼저 배당받을 가능성이 있습니다.",
    basis: "권리분석 API 연동 전 샘플",
  },
  {
    code: "HIGH_DEPOSIT_RATIO",
    title: "높은 보증금비율",
    severity: "medium",
    description:
      "보증금이 참고 주택가액의 약 90.9%로, 보증금 회수 여유가 크지 않습니다.",
    basis: "계약 예정 보증금 2억 원 ÷ 참고가액 2억 2천만 원",
  },
];

const baseRequiredChecks: RequiredCheck[] = [
  {
    code: "JOINT_COLLATERAL_UNKNOWN",
    title: "공동담보 여부 확인 필요",
    severity: "check",
    description:
      "다른 부동산이 같은 채무의 담보로 함께 설정됐는지 아직 확인되지 않았습니다.",
    action: "등기부의 공동담보 목록을 확인하세요.",
  },
  {
    code: "REFERENCE_VALUE_UNVERIFIED",
    title: "주택가액 산정 근거 확인 필요",
    severity: "check",
    description:
      "현재 참고가액은 개발용 샘플이며 실제 분석에 사용할 공식 근거가 필요합니다.",
    action: "공식 또는 검증된 주택가액과 기준일을 확인하세요.",
  },
];

const confidenceByGuaranteeStatus: Record<GuaranteeStatus, number> = {
  estimated_eligible: 60,
  officially_eligible: 75,
  applied: 75,
  enrolled: 85,
  ineligible: 60,
  unknown: 50,
};

function determineRiskStage(
  confirmedRisks: ConfirmedRisk[],
  requiredChecks: RequiredCheck[],
): RiskStage {
  const highCount = confirmedRisks.filter(
    (risk) => risk.severity === "high",
  ).length;
  const mediumCount = confirmedRisks.filter(
    (risk) => risk.severity === "medium",
  ).length;

  if (highCount >= 2) return "계약 전 재검토";
  if (highCount === 1 || mediumCount >= 2) return "주의";
  if (confirmedRisks.length || requiredChecks.length) return "추가 확인 필요";
  return "기본 확인";
}

export function buildAnalysisSample(
  guaranteeStatus: GuaranteeStatus,
): AnalysisResult {
  const confirmedRisks = [...baseConfirmedRisks];
  const requiredChecks = [...baseRequiredChecks];

  if (guaranteeStatus === "ineligible") {
    confirmedRisks.push({
      code: "GUARANTEE_INELIGIBLE",
      title: "반환보증 가입 어려움",
      severity: "high",
      description:
        "반환보증 가입이 어렵거나 불가한 상태로 추가 계약조건 검토가 필요합니다.",
      basis: "반환보증 API 연동 전 샘플",
    });
  }

  if (
    guaranteeStatus === "estimated_eligible" ||
    guaranteeStatus === "unknown"
  ) {
    requiredChecks.push({
      code: "GUARANTEE_STATUS_UNCONFIRMED",
      title: "반환보증 가입 가능 여부 확인 필요",
      severity: "check",
      description:
        "현재 반환보증 가입 가능 여부를 공식적으로 확정하지 못했습니다.",
      action: "계약 전에 공식 사전확인을 진행하세요.",
    });
  }

  if (
    guaranteeStatus === "officially_eligible" ||
    guaranteeStatus === "applied"
  ) {
    requiredChecks.push({
      code: "GUARANTEE_ENROLLMENT_PENDING",
      title: "반환보증 가입 완료 확인 필요",
      severity: "check",
      description:
        "가입 가능 확인 또는 신청 단계이며 실제 가입 완료 상태는 아닙니다.",
      action: "최종 보증서와 가입 완료 여부를 확인하세요.",
    });
  }

  return {
    riskStage: determineRiskStage(confirmedRisks, requiredChecks),
    confirmedRisks,
    requiredChecks,
    analysisConfidence: confidenceByGuaranteeStatus[guaranteeStatus],
  };
}

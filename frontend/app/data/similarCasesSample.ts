import type { GuaranteeStatus } from "./guaranteeStates";

export type CaseFactor = {
  label: string;
  description: string;
  kind: "match" | "difference";
};

export type SimilarCase = {
  id: string;
  title: string;
  category: string;
  similarity: number;
  summary: string;
  factors: CaseFactor[];
  plainExplanation: string;
  sourceName: string;
  referenceDate: string;
};

function buildGuaranteeFactor(status: GuaranteeStatus): CaseFactor {
  if (status === "enrolled") {
    return {
      label: "반환보증 가입 완료",
      description:
        "유사사례와 달리 현재 매물은 반환보증 가입 완료가 확인된 점이 중요한 차이입니다.",
      kind: "difference",
    };
  }

  if (status === "ineligible") {
    return {
      label: "반환보증 가입 어려움",
      description:
        "보증금 반환을 보완할 보호장치를 확보하기 어려운 조건이 유사합니다.",
      kind: "match",
    };
  }

  if (status === "officially_eligible" || status === "applied") {
    return {
      label: "반환보증 가입 완료 전",
      description:
        "가입 가능 확인 또는 신청 단계일 뿐 실제 가입 완료 전이라는 점이 유사합니다.",
      kind: "match",
    };
  }

  return {
    label: "반환보증 상태 미확정",
    description:
      "계약 시점에 반환보증이라는 보호장치를 확정하지 못한 조건이 유사합니다.",
    kind: "match",
  };
}

export function buildSimilarCasesSample(
  guaranteeStatus: GuaranteeStatus,
): SimilarCase[] {
  const guaranteeFactor = buildGuaranteeFactor(guaranteeStatus);
  const firstSimilarity = guaranteeStatus === "enrolled" ? 72 : 86;

  return [
    {
      id: "CASE-MORTGAGE-001",
      title: "근저당 말소 약속을 확인하지 못한 계약 상담",
      category: "근저당 · 보증금 반환",
      similarity: firstSimilarity,
      summary:
        "임차인은 잔금일에 근저당을 말소하겠다는 설명을 들었지만, 등기부에서 말소 완료를 확인하기 전에 계약을 진행했습니다. 이후 보증금 반환이 늦어져 대응 방법을 문의한 상담 사례입니다.",
      factors: [
        {
          label: "선순위 근저당 존재",
          description:
            "은행 등 선순위 권리자가 보증금보다 먼저 배당받을 수 있는 구조가 유사합니다.",
          kind: "match",
        },
        {
          label: "보증금이 참고가액에 가까움",
          description:
            "주택가액이 내려가거나 처분비용이 발생하면 보증금 회수 여유가 줄어드는 조건이 유사합니다.",
          kind: "match",
        },
        guaranteeFactor,
      ],
      plainExplanation:
        "집에 문제가 생겨 경매로 넘어가면 은행이 먼저 돈을 받아갈 수 있습니다. 보증금도 집값에 가까워 남는 돈의 여유가 크지 않습니다. 집주인의 ‘말소하겠다’는 말은 완료된 사실이 아니므로, 잔금을 보내기 전에 최신 등기부에서 실제 말소 여부를 확인해야 합니다.",
      sourceName: "AI 상담사례 API 연동 전 샘플",
      referenceDate: "2026-07-25",
    },
    {
      id: "CASE-DEPOSIT-002",
      title: "주택가액에 가까운 보증금으로 계약을 재검토한 상담",
      category: "높은 보증금비율 · 다세대주택",
      similarity: 78,
      summary:
        "다세대주택 전세계약을 앞둔 임차인이 제시된 주택가액을 그대로 믿어도 되는지, 다른 담보가 있는지 확인하지 못한 상태에서 계약 진행 여부를 문의한 사례입니다.",
      factors: [
        {
          label: "높은 보증금비율",
          description:
            "계약 예정 보증금이 참고 주택가액의 약 90.9%인 구조가 유사합니다.",
          kind: "match",
        },
        {
          label: "공동담보 여부 미확인",
          description:
            "같은 채무에 다른 부동산이 함께 담보로 묶였는지 확인하지 못한 점이 유사합니다.",
          kind: "match",
        },
        {
          label: "참고가액 근거 미확인",
          description:
            "실제 계약 판단에 사용할 공식 주택가액과 기준일을 다시 확인해야 하는 점이 유사합니다.",
          kind: "match",
        },
      ],
      plainExplanation:
        "보증금이 집값과 너무 가까우면 집을 팔아도 세금과 비용을 빼고 보증금을 모두 돌려주기 어려울 수 있습니다. 먼저 집값의 근거가 믿을 만한지 확인하고, 등기부의 공동담보 목록까지 살펴본 뒤 계약 조건을 다시 비교하는 것이 좋습니다.",
      sourceName: "AI 상담사례 API 연동 전 샘플",
      referenceDate: "2026-07-25",
    },
  ];
}

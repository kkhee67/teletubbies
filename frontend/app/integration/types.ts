export type UnknownRecord = Record<string, unknown>;

export type GuaranteeProductType =
  | "jeonse_return"
  | "rental_deposit"
  | "unknown";

export type PropertySearchItem = {
  propertyId: string;
  addressDisplay: string | null;
  district: string | null;
  housingType: string | null;
  referenceValue: number | null;
  guaranteeStatus: string | null;
  guaranteeProductType: GuaranteeProductType | null;
};

export type AnalyzeRequestPayload = {
  property_id: string;
  address_query: string;
  planned_deposit: number;
  monthly_rent: number;
  guarantee_product_type?: GuaranteeProductType;
  user_note: string;
  user_corrections?: Record<string, string | number | boolean>;
};

export type SearchAndAnalyzeInput = {
  address: string;
  plannedDeposit: number;
  monthlyRent?: number;
  userNote?: string;
  userCorrections?: Record<string, string | number | boolean>;
};

export type ApiClientOptions = {
  baseUrl?: string;
  signal?: AbortSignal;
  fetcher?: typeof fetch;
};

export type PropertyFieldStatus =
  | "neutral"
  | "stable"
  | "warning"
  | "check";

export type PropertyFieldViewModel = {
  key: string;
  label: string;
  value: string | number | boolean | null;
  description: string | null;
  sourceName: string | null;
  referenceDate: string | null;
  status: PropertyFieldStatus;
};

export type PropertySummaryViewModel = {
  propertyId: string | null;
  addressDisplay: string | null;
  district: string | null;
  housingType: string | null;
  referenceValue: number | null;
  plannedDeposit: number | null;
  monthlyRent: number | null;
  depositRatio: number | null;
  mortgageStatus: string | null;
  seizureStatus: string | null;
  jointCollateral: string | null;
  guaranteeStatus: string | null;
  valueSource: string | null;
  fields: PropertyFieldViewModel[];
};

export type GuaranteeStatus =
  | "estimated_eligible"
  | "officially_eligible"
  | "applied"
  | "enrolled"
  | "ineligible"
  | "unknown";

export type GuaranteeGroup =
  | "check_required"
  | "in_progress"
  | "protected"
  | "deep_analysis";

export type GuaranteeViewModel = {
  status: GuaranteeStatus | null;
  rawStatus: string | null;
  branch: string | null;
  propertyStatus: string | null;
  group: GuaranteeGroup | null;
  displayText: string | null;
  message: string | null;
  disclaimer: string | null;
  nextActions: string[];
};

export type RiskSeverity =
  | "critical"
  | "high"
  | "medium"
  | "low"
  | "check"
  | "unknown";

export type RiskSignalViewModel = {
  code: string | null;
  title: string | null;
  severity: RiskSeverity;
  description: string | null;
  basis: string | null;
  action: string | null;
  includedInRiskScore: boolean | null;
};

export type ChecklistItemViewModel = {
  code: string | null;
  title: string | null;
  description: string | null;
  priority: string | null;
  status: string | null;
};

export type RecommendedActionViewModel = {
  label: string | null;
  description: string | null;
};

export type RiskAnalysisViewModel = {
  riskStage: string | null;
  analysisConfidence: number | null;
  signals: RiskSignalViewModel[];
  confirmedRisks: RiskSignalViewModel[];
  requiredChecks: RiskSignalViewModel[];
  referenceSignals: RiskSignalViewModel[];
  checklist: ChecklistItemViewModel[];
  recommendedAction: RecommendedActionViewModel | null;
  notice: string | null;
  disclaimer: string | null;
};

export type SimilarCaseFactorViewModel = {
  label: string | null;
  description: string | null;
  kind: "match" | "difference" | "unknown";
};

export type SimilarCaseViewModel = {
  id: string | null;
  title: string | null;
  category: string | null;
  similarity: number | null;
  summary: string | null;
  tags: string[];
  factors: SimilarCaseFactorViewModel[];
  missedChecks: string[];
  plainExplanation: string | null;
  sourceName: string | null;
  referenceDate: string | null;
};

export type AiApiStatus =
  | "ok"
  | "fallback"
  | "disabled"
  | "unavailable"
  | "timeout"
  | "error"
  | "local_mock"
  | "unsupported_product_type"
  | "unknown";

export type AnalysisViewModel = {
  propertySummary: PropertySummaryViewModel;
  guarantee: GuaranteeViewModel;
  riskAnalysis: RiskAnalysisViewModel;
  similarCases: SimilarCaseViewModel[];
  checklist: ChecklistItemViewModel[];
  aiApiStatus: AiApiStatus;
  aiApiMessage: string | null;
  generatedAt: string | null;
};

export type SearchAndAnalyzeResult = {
  propertyId: string;
  searchItem: PropertySearchItem;
  analysis: AnalysisViewModel;
  rawAnalysisResponse: unknown;
};

import type {
  AiApiStatus,
  AnalysisViewModel,
  ChecklistItemViewModel,
  GuaranteeGroup,
  GuaranteeStatus,
  GuaranteeViewModel,
  PropertyFieldStatus,
  PropertyFieldViewModel,
  PropertySearchItem,
  PropertySummaryViewModel,
  RecommendedActionViewModel,
  RiskAnalysisViewModel,
  RiskSeverity,
  RiskSignalViewModel,
  SimilarCaseFactorViewModel,
  SimilarCaseViewModel,
  UnknownRecord,
} from "./types";

function asRecord(value: unknown): UnknownRecord | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as UnknownRecord)
    : null;
}

function pick(record: UnknownRecord | null, ...keys: string[]): unknown {
  if (!record) return undefined;

  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(record, key)) {
      const value = record[key];
      if (value !== undefined && value !== null) return value;
    }
  }

  return undefined;
}

function toStringOrNull(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

function toNumberOrNull(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value !== "string" || value.trim() === "") return null;

  const normalized = Number(value.replaceAll(",", ""));
  return Number.isFinite(normalized) ? normalized : null;
}

function toBooleanOrNull(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map(toStringOrNull)
    .filter((item): item is string => item !== null);
}

function toRecordArray(value: unknown): UnknownRecord[] {
  if (!Array.isArray(value)) return [];
  return value
    .map(asRecord)
    .filter((item): item is UnknownRecord => item !== null);
}

function unwrapFieldValue(value: unknown): unknown {
  const field = asRecord(value);
  return field ? pick(field, "value", "amount", "status") : value;
}

function fieldSourceName(value: unknown, fallback: string | null): string | null {
  const field = asRecord(value);
  return (
    toStringOrNull(pick(field, "source_name", "sourceName", "source")) ??
    fallback
  );
}

function fieldReferenceDate(
  value: unknown,
  fallback: string | null,
): string | null {
  const field = asRecord(value);
  return (
    toStringOrNull(
      pick(field, "reference_date", "referenceDate", "generated_at"),
    ) ?? fallback
  );
}

function normalizeKnownStatus(value: unknown): string | null {
  return toStringOrNull(unwrapFieldValue(value))?.toLowerCase() ?? null;
}

function propertyStatus(
  key: "housing" | "reference" | "mortgage" | "seizure" | "collateral",
  value: unknown,
): PropertyFieldStatus {
  if (key === "reference" && toNumberOrNull(value) !== null) return "neutral";

  const normalized = normalizeKnownStatus(value);
  if (normalized === null || normalized === "unknown") return "check";

  if (key === "mortgage") {
    if (normalized === "none" || normalized === "removed") return "stable";
    if (normalized === "exists" || normalized === "promised_removal") {
      return "warning";
    }
  }

  if (key === "seizure" || key === "collateral") {
    if (normalized === "none") return "stable";
    if (normalized === "exists") return "warning";
  }

  return "neutral";
}

function propertyField(
  source: UnknownRecord,
  keys: string[],
  label: string,
  statusKind:
    | "housing"
    | "reference"
    | "mortgage"
    | "seizure"
    | "collateral",
  fallbackSource: string | null,
  fallbackDate: string | null,
  description: string | null = null,
): PropertyFieldViewModel {
  const rawValue = pick(source, ...keys);
  const value = unwrapFieldValue(rawValue);
  const scalarValue =
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
      ? value
      : null;

  return {
    key: keys[0],
    label,
    value: scalarValue,
    description,
    sourceName: fieldSourceName(rawValue, fallbackSource),
    referenceDate: fieldReferenceDate(rawValue, fallbackDate),
    status: propertyStatus(statusKind, value),
  };
}

function findSearchItems(payload: unknown): unknown[] {
  if (Array.isArray(payload)) return payload;

  const root = asRecord(payload);
  const direct = pick(root, "items", "results", "properties");
  if (Array.isArray(direct)) return direct;

  const rawData = pick(root, "data");
  if (Array.isArray(rawData)) return rawData;

  const data = asRecord(rawData);
  const nested = pick(data, "items", "results", "properties");
  if (Array.isArray(nested)) return nested;

  return [];
}

export function adaptPropertySearchResponse(
  payload: unknown,
): PropertySearchItem[] {
  return findSearchItems(payload)
    .map(asRecord)
    .filter((item): item is UnknownRecord => item !== null)
    .map((item) => ({
      propertyId:
        toStringOrNull(pick(item, "property_id", "propertyId", "id")) ?? "",
      addressDisplay: toStringOrNull(
        pick(item, "address_display", "display_address", "addressDisplay"),
      ),
      district: toStringOrNull(pick(item, "district")),
      housingType: toStringOrNull(
        pick(item, "housing_type", "property_type", "housingType"),
      ),
      referenceValue: toNumberOrNull(
        pick(item, "reference_value", "referenceValue"),
      ),
      guaranteeStatus: toStringOrNull(
        pick(item, "guarantee_status", "guaranteeStatus"),
      ),
      guaranteeProductType: normalizeGuaranteeProductType(
        pick(item, "guarantee_product_type", "guaranteeProductType"),
      ),
    }))
    .filter((item) => item.propertyId !== "");
}

function normalizeGuaranteeProductType(
  value: unknown,
): PropertySearchItem["guaranteeProductType"] {
  const normalized = normalizeKnownStatus(value);
  if (
    normalized === "jeonse_return" ||
    normalized === "rental_deposit" ||
    normalized === "unknown"
  ) {
    return normalized;
  }
  return null;
}

function normalizeAiApiStatus(value: unknown): AiApiStatus {
  const normalized = normalizeKnownStatus(value);
  if (
    normalized === "ok" ||
    normalized === "fallback" ||
    normalized === "disabled" ||
    normalized === "unavailable" ||
    normalized === "timeout" ||
    normalized === "error" ||
    normalized === "local_mock" ||
    normalized === "unsupported_product_type"
  ) {
    return normalized;
  }
  return "unknown";
}

function adaptPropertySummary(root: UnknownRecord): PropertySummaryViewModel {
  const source =
    asRecord(pick(root, "property_summary", "propertySummary")) ??
    asRecord(pick(root, "property")) ??
    {};
  const valueSource = toStringOrNull(
    pick(source, "value_source", "valueSource", "source_name"),
  );
  const referenceValueRaw = pick(
    source,
    "reference_value",
    "referenceValue",
  );
  const depositNotice = toStringOrNull(
    pick(source, "deposit_ratio_notice", "depositRatioNotice"),
  );

  return {
    propertyId: toStringOrNull(
      pick(source, "property_id", "propertyId", "id"),
    ),
    addressDisplay: toStringOrNull(
      pick(
        source,
        "address_display",
        "display_address",
        "addressDisplay",
        "address",
      ),
    ),
    district: toStringOrNull(pick(source, "district")),
    housingType: normalizeKnownStatus(
      pick(source, "housing_type", "property_type", "housingType"),
    ),
    referenceValue: toNumberOrNull(unwrapFieldValue(referenceValueRaw)),
    plannedDeposit: toNumberOrNull(
      pick(source, "planned_deposit", "plannedDeposit"),
    ),
    monthlyRent: toNumberOrNull(
      pick(source, "monthly_rent", "monthlyRent"),
    ),
    depositRatio: toNumberOrNull(
      pick(source, "deposit_ratio", "depositRatio"),
    ),
    mortgageStatus: normalizeKnownStatus(
      pick(source, "mortgage_status", "mortgageStatus"),
    ),
    seizureStatus: normalizeKnownStatus(
      pick(source, "seizure_status", "seizureStatus"),
    ),
    jointCollateral: normalizeKnownStatus(
      pick(source, "joint_collateral", "jointCollateral"),
    ),
    guaranteeStatus: normalizeKnownStatus(
      pick(source, "guarantee_status", "guaranteeStatus"),
    ),
    valueSource,
    fields: [
      propertyField(
        source,
        ["housing_type", "property_type", "housingType"],
        "주택유형",
        "housing",
        null,
        null,
      ),
      propertyField(
        source,
        ["reference_value", "referenceValue"],
        "참고 주택가액",
        "reference",
        valueSource,
        null,
        depositNotice,
      ),
      propertyField(
        source,
        ["mortgage_status", "mortgageStatus"],
        "근저당",
        "mortgage",
        null,
        null,
      ),
      propertyField(
        source,
        ["seizure_status", "seizureStatus"],
        "압류·가압류",
        "seizure",
        null,
        null,
      ),
      propertyField(
        source,
        ["joint_collateral", "jointCollateral"],
        "공동담보",
        "collateral",
        null,
        null,
      ),
    ],
  };
}

function normalizeGuaranteeStatus(value: string | null): GuaranteeStatus | null {
  if (
    value === "estimated_eligible" ||
    value === "officially_eligible" ||
    value === "applied" ||
    value === "enrolled" ||
    value === "ineligible" ||
    value === "unknown"
  ) {
    return value;
  }

  // The legacy three-state API does not prove enrollment or official approval.
  if (value === "eligible") return "estimated_eligible";
  return null;
}

function normalizeGuaranteeGroup(value: string | null): GuaranteeGroup | null {
  if (value === "confirmation_required" || value === "check_required") {
    return "check_required";
  }
  if (
    value === "in_progress" ||
    value === "protected" ||
    value === "deep_analysis"
  ) {
    return value;
  }
  return null;
}

function groupFromStatus(status: GuaranteeStatus | null): GuaranteeGroup | null {
  if (status === "estimated_eligible" || status === "unknown") {
    return "check_required";
  }
  if (status === "officially_eligible" || status === "applied") {
    return "in_progress";
  }
  if (status === "enrolled") return "protected";
  if (status === "ineligible") return "deep_analysis";
  return null;
}

function adaptGuarantee(
  root: UnknownRecord,
  property: PropertySummaryViewModel,
): GuaranteeViewModel {
  const source = asRecord(pick(root, "guarantee")) ?? {};
  const branch = normalizeKnownStatus(
    pick(root, "guarantee_branch", "guaranteeBranch"),
  );
  const propertyStatus = property.guaranteeStatus;
  const rawStatus =
    normalizeKnownStatus(pick(source, "status")) ??
    branch ??
    propertyStatus;
  const status = normalizeGuaranteeStatus(rawStatus);
  const group =
    normalizeGuaranteeGroup(
      normalizeKnownStatus(pick(source, "group", "status_group")),
    ) ?? groupFromStatus(status);

  return {
    status,
    rawStatus,
    branch,
    propertyStatus,
    group,
    displayText: toStringOrNull(
      pick(source, "display_text", "displayText", "label"),
    ),
    message:
      toStringOrNull(pick(source, "message")) ??
      toStringOrNull(pick(root, "guarantee_message", "guaranteeMessage")),
    disclaimer:
      toStringOrNull(pick(source, "disclaimer")) ??
      toStringOrNull(
        pick(root, "guarantee_disclaimer", "guaranteeDisclaimer"),
      ),
    nextActions: toStringArray(
      pick(source, "next_actions", "nextActions", "actions"),
    ),
  };
}

function normalizeSeverity(value: unknown): RiskSeverity {
  const severity = normalizeKnownStatus(value);
  if (
    severity === "critical" ||
    severity === "high" ||
    severity === "medium" ||
    severity === "low" ||
    severity === "check"
  ) {
    return severity;
  }
  return "unknown";
}

function adaptRiskSignal(item: UnknownRecord): RiskSignalViewModel {
  return {
    code: toStringOrNull(pick(item, "code", "signal_code", "signalCode")),
    title: toStringOrNull(pick(item, "title", "label", "name")),
    severity: normalizeSeverity(pick(item, "severity", "priority")),
    description: toStringOrNull(
      pick(item, "explanation", "description", "message"),
    ),
    basis: toStringOrNull(pick(item, "basis", "source", "reason")),
    action: toStringOrNull(
      pick(item, "action", "recommended_action", "recommendedAction"),
    ),
    includedInRiskScore: toBooleanOrNull(
      pick(item, "included_in_risk_score", "includedInRiskScore"),
    ),
  };
}

function looksLikeRequiredCheck(signal: RiskSignalViewModel): boolean {
  if (signal.severity === "check") return true;
  const code = (signal.code ?? "").toUpperCase();
  return /(?:UNKNOWN|UNVERIFIED|UNCONFIRMED|NOT_COMPLETED|PENDING|ESTIMATED_ONLY|CHECK_REQUIRED)/.test(
    code,
  );
}

function adaptChecklist(value: unknown): ChecklistItemViewModel[] {
  return toRecordArray(value).map((item) => ({
    code: toStringOrNull(pick(item, "code", "id", "check_id", "checkId")),
    title: toStringOrNull(pick(item, "title", "label", "name")),
    description: toStringOrNull(
      pick(item, "description", "explanation", "action"),
    ),
    priority: toStringOrNull(pick(item, "priority", "severity")),
    status: toStringOrNull(pick(item, "status", "state")),
  }));
}

function adaptRecommendedAction(
  value: unknown,
): RecommendedActionViewModel | null {
  const text = toStringOrNull(value);
  if (text) return { label: text, description: null };

  const source = asRecord(value);
  if (!source) return null;
  const result = {
    label: toStringOrNull(pick(source, "label", "title", "action")),
    description: toStringOrNull(
      pick(source, "description", "message", "explanation"),
    ),
  };
  return result.label || result.description ? result : null;
}

function adaptRiskAnalysis(
  root: UnknownRecord,
  checklist: ChecklistItemViewModel[],
): RiskAnalysisViewModel {
  const source = asRecord(pick(root, "analysis")) ?? root;
  const signals = toRecordArray(pick(source, "signals")).map(adaptRiskSignal);
  const explicitConfirmedValue = pick(
    source,
    "confirmed_risks",
    "confirmedRisks",
  );
  const explicitChecksValue = pick(
    source,
    "required_checks",
    "requiredChecks",
  );
  const explicitConfirmed =
    toRecordArray(explicitConfirmedValue).map(adaptRiskSignal);
  const explicitChecks = toRecordArray(explicitChecksValue).map(adaptRiskSignal);
  const confirmedRisks =
    Array.isArray(explicitConfirmedValue)
      ? explicitConfirmed
      : signals.filter(
          (signal) =>
            !looksLikeRequiredCheck(signal) &&
            signal.includedInRiskScore !== false,
        );
  const requiredChecks =
    Array.isArray(explicitChecksValue)
      ? explicitChecks
      : signals.filter(looksLikeRequiredCheck);

  const displayedSignalKeys = new Set(
    [...confirmedRisks, ...requiredChecks].map(
      (signal) => `${signal.code ?? ""}:${signal.title ?? ""}:${signal.severity}`,
    ),
  );
  const referenceSignals = signals.filter(
    (signal) =>
      !displayedSignalKeys.has(
        `${signal.code ?? ""}:${signal.title ?? ""}:${signal.severity}`,
      ),
  );

  return {
    riskStage: toStringOrNull(pick(source, "risk_stage", "riskStage")),
    analysisConfidence: toNumberOrNull(
      pick(source, "analysis_confidence", "analysisConfidence"),
    ),
    signals,
    confirmedRisks,
    requiredChecks,
    referenceSignals,
    checklist,
    recommendedAction: adaptRecommendedAction(
      pick(root, "recommended_action", "recommendedAction"),
    ),
    notice: toStringOrNull(
      pick(source, "notice", "basic_stage_notice", "basicStageNotice"),
    ),
    disclaimer: toStringOrNull(pick(root, "disclaimer")),
  };
}

function adaptCaseFactor(value: UnknownRecord): SimilarCaseFactorViewModel {
  const rawKind = normalizeKnownStatus(pick(value, "kind", "type"));
  const kind =
    rawKind === "match" || rawKind === "difference" ? rawKind : "unknown";

  return {
    label: toStringOrNull(pick(value, "label", "title", "name")),
    description: toStringOrNull(
      pick(value, "description", "explanation", "message"),
    ),
    kind,
  };
}

function adaptSimilarCases(root: UnknownRecord): SimilarCaseViewModel[] {
  const explanation = asRecord(
    pick(root, "easy_explanation", "easyExplanation"),
  );
  const selectedCaseId = toStringOrNull(
    pick(explanation, "selected_case_id", "selectedCaseId"),
  );
  const plainExplanation = toStringOrNull(
    pick(explanation, "plain_explanation", "plainExplanation"),
  );

  return toRecordArray(pick(root, "similar_cases", "similarCases")).map(
    (item) => {
      const id = toStringOrNull(pick(item, "case_id", "caseId", "id"));
      return {
        id,
        title: toStringOrNull(pick(item, "title")),
        category: toStringOrNull(pick(item, "category", "type")),
        similarity: toNumberOrNull(
          pick(item, "similarity", "similarity_score", "similarityScore"),
        ),
        summary: toStringOrNull(
          pick(item, "summary", "what_happened", "whatHappened"),
        ),
        tags: toStringArray(pick(item, "tags")),
        factors: toRecordArray(pick(item, "factors")).map(adaptCaseFactor),
        missedChecks: toStringArray(
          pick(item, "missed_checks", "missedChecks"),
        ),
        plainExplanation:
          id !== null && id === selectedCaseId ? plainExplanation : null,
        sourceName: toStringOrNull(
          pick(item, "source_name", "sourceName", "source"),
        ),
        referenceDate: toStringOrNull(
          pick(item, "reference_date", "referenceDate"),
        ),
      };
    },
  );
}

function hasAnalysisShape(record: UnknownRecord): boolean {
  return [
    "property_summary",
    "propertySummary",
    "property",
    "guarantee_branch",
    "guaranteeBranch",
    "guarantee",
    "risk_stage",
    "riskStage",
    "analysis",
  ].some((key) => Object.prototype.hasOwnProperty.call(record, key));
}

export function adaptAnalyzeResponse(payload: unknown): AnalysisViewModel {
  const envelope = asRecord(payload) ?? {};
  const nested =
    asRecord(pick(envelope, "data", "result", "analysis_result")) ?? null;
  const root =
    !hasAnalysisShape(envelope) && nested !== null ? nested : envelope;
  const checklist = adaptChecklist(pick(root, "checklist"));
  const propertySummary = adaptPropertySummary(root);

  return {
    propertySummary,
    guarantee: adaptGuarantee(root, propertySummary),
    riskAnalysis: adaptRiskAnalysis(root, checklist),
    similarCases: adaptSimilarCases(root),
    checklist,
    aiApiStatus: normalizeAiApiStatus(
      pick(root, "ai_api_status", "aiApiStatus") ??
        pick(envelope, "ai_api_status", "aiApiStatus"),
    ),
    aiApiMessage:
      toStringOrNull(pick(root, "ai_api_message", "aiApiMessage")) ??
      toStringOrNull(pick(envelope, "ai_api_message", "aiApiMessage")),
    generatedAt: toStringOrNull(
      pick(root, "generated_at", "generatedAt"),
    ),
  };
}

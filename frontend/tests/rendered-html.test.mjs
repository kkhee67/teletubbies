import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { after, before, test } from "node:test";
import { createServer } from "vite";

const frontendRootUrl = new URL("../", import.meta.url);
const frontendRootPath = fileURLToPath(frontendRootUrl);
let integration;
let vite;

before(async () => {
  vite = await createServer({
    root: frontendRootPath,
    configFile: false,
    server: { middlewareMode: true },
    appType: "custom",
    logLevel: "silent",
  });
  integration = await vite.ssrLoadModule("/app/integration/index.ts");
});

after(async () => {
  await vite?.close();
});

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

function jsonResponse(payload, init = {}) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
    ...init,
  });
}

const analyzeResponse = {
  ai_api_status: "ok",
  ai_api_message: null,
  guarantee: {
    status: "estimated_eligible",
    group: "check_required",
    display_text: "가입 가능성 추정",
    message: "반환보증 가입 가능성을 확인했습니다.",
    next_actions: ["보증기관에서 공식 가입 가능 여부 확인"],
  },
  guarantee_branch: "check_required",
  guarantee_message: "반환보증 가입 가능성을 확인했습니다.",
  guarantee_disclaimer: "가입 완료 여부는 보증기관에서 다시 확인해 주세요.",
  risk_stage: "caution",
  analysis_confidence: 73,
  signals: [
    {
      code: "MORTGAGE_EXISTS",
      title: "근저당 확인",
      severity: "high",
      explanation: "등기부에 근저당이 확인됩니다.",
      action: "말소 조건을 특약에 적으세요.",
      included_in_risk_score: true,
    },
    {
      code: "REGISTRY_UNKNOWN",
      title: "최신 등기 확인 필요",
      severity: "check",
      explanation: "최신 등기 정보가 아직 없습니다.",
      action: "계약 당일 다시 발급하세요.",
      included_in_risk_score: false,
    },
    {
      code: "HOUSING_TYPE_PATTERN",
      title: "주택유형 참고 신호",
      severity: "low",
      explanation: "주택유형에 따른 참고 정보입니다.",
      action: "주택유형별 확인사항을 살펴보세요.",
      included_in_risk_score: false,
    },
  ],
  checklist: [
    {
      code: "CHECK_REGISTRY",
      title: "최신 등기부 확인",
      description: "계약 당일 등기부를 다시 발급합니다.",
      priority: "high",
    },
  ],
  recommended_action: {
    label: "조건 확인 후 진행",
    description: "근저당 말소 조건을 서면으로 확인하세요.",
  },
  property_summary: {
    property_id: "P001",
    address_display: "부산광역시 수영구 광안동 1-1",
    district: "수영구",
    housing_type: "apartment",
    reference_value: 350000000,
    planned_deposit: 200000000,
    monthly_rent: 0,
    deposit_ratio: 0.5714,
    mortgage_status: "exists",
    seizure_status: "none",
    joint_collateral: "unknown",
    guarantee_status: "estimated_eligible",
    guarantee_product_type: "jeonse_return",
    value_source: "team-api",
  },
  similar_cases: [
    {
      case_id: "CASE-1",
      similarity: 0.82,
      tags: ["근저당"],
      summary: "말소 약속을 확인하지 않아 문제가 생긴 사례입니다.",
      missed_checks: ["말소 특약"],
      source: "상담사례",
    },
  ],
  easy_explanation: {
    selected_case_id: "CASE-1",
    plain_explanation: "계약서에 말소 약속을 구체적으로 적어야 합니다.",
  },
  generated_at: "2026-07-25T12:00:00Z",
  disclaimer: "이 분석은 계약 안전을 보증하지 않습니다.",
};

const firstSearchItem = {
  property_id: "P001",
  address_display: "부산광역시 수영구 광안동 1-1",
  district: "수영구",
  housing_type: "apartment",
  reference_value: 350000000,
  guarantee_status: "estimated_eligible",
  guarantee_product_type: "jeonse_return",
};

test("server-renders the live-analysis entry screen", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>안심계약 레이더<\/title>/i);
  assert.match(html, /계약할 매물을 알려주세요/);
  assert.match(html, /DIVE 2026/);
  assert.doesNotMatch(html, /DIVE 2026 MVP|API 연결 전 샘플|개발용 샘플/);
});

test("uses the configured API base URL and the localhost default", () => {
  const previous = process.env.NEXT_PUBLIC_API_BASE_URL;

  try {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    assert.equal(
      integration.getApiBaseUrl(),
      "http://127.0.0.1:8000",
    );
    assert.equal(
      integration.getApiBaseUrl("https://api.example.com///"),
      "https://api.example.com",
    );
  } finally {
    if (previous === undefined) {
      delete process.env.NEXT_PUBLIC_API_BASE_URL;
    } else {
      process.env.NEXT_PUBLIC_API_BASE_URL = previous;
    }
  }
});

test("automatically analyzes a single address-search result", async () => {
  const calls = [];
  const fetcher = async (input, init) => {
    calls.push({ input: String(input), init });
    return calls.length === 1
      ? jsonResponse({ items: [firstSearchItem] })
      : jsonResponse(analyzeResponse);
  };

  const result = await integration.searchAndAnalyze(
    {
      address: " 부산 수영구 광안동 1-1 ",
      plannedDeposit: 200000000,
      monthlyRent: 0,
      userNote: "잔금일에 근저당을 말소한다고 들었습니다.",
    },
    {
      baseUrl: "https://api.example.com/",
      fetcher,
    },
  );

  assert.equal(calls.length, 2);
  const searchUrl = new URL(calls[0].input);
  assert.equal(searchUrl.origin, "https://api.example.com");
  assert.equal(searchUrl.pathname, "/properties/search");
  assert.equal(searchUrl.searchParams.get("q"), "부산 수영구 광안동 1-1");
  assert.equal(calls[0].init.method, "GET");

  assert.equal(calls[1].input, "https://api.example.com/analyze");
  assert.equal(calls[1].init.method, "POST");
  assert.equal(calls[1].init.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(calls[1].init.body), {
    property_id: "P001",
    address_query: "부산 수영구 광안동 1-1",
    planned_deposit: 200000000,
    monthly_rent: 0,
    guarantee_product_type: "jeonse_return",
    user_note: "잔금일에 근저당을 말소한다고 들었습니다.",
  });

  assert.equal(result.propertyId, "P001");
  assert.equal(result.analysis.propertySummary.propertyId, "P001");
  assert.equal(result.analysis.guarantee.rawStatus, "estimated_eligible");
  assert.equal(result.analysis.guarantee.branch, "check_required");
  assert.equal(
    result.analysis.guarantee.propertyStatus,
    "estimated_eligible",
  );
  assert.equal(result.analysis.guarantee.status, "estimated_eligible");
  assert.equal(result.analysis.guarantee.group, "check_required");
  assert.equal(result.analysis.riskAnalysis.riskStage, "caution");
  assert.equal(result.analysis.riskAnalysis.analysisConfidence, 73);
  assert.equal(result.analysis.riskAnalysis.confirmedRisks.length, 1);
  assert.equal(result.analysis.riskAnalysis.requiredChecks.length, 1);
  assert.equal(result.analysis.riskAnalysis.referenceSignals.length, 1);
  assert.equal(result.analysis.checklist[0].code, "CHECK_REGISTRY");
  assert.equal(
    result.analysis.riskAnalysis.recommendedAction.label,
    "조건 확인 후 진행",
  );
  assert.equal(
    result.analysis.similarCases[0].plainExplanation,
    "계약서에 말소 약속을 구체적으로 적어야 합니다.",
  );
  assert.equal(result.analysis.aiApiStatus, "ok");
  assert.equal(result.analysis.aiApiMessage, null);
});

test("requires an explicit selection when address search returns multiple properties", async () => {
  let callCount = 0;
  const searchPayload = {
    items: [
      firstSearchItem,
      {
        ...firstSearchItem,
        property_id: "P002",
        address_display: "부산광역시 강서구 샘플로 12",
        guarantee_product_type: "rental_deposit",
      },
    ],
  };
  const searchFetcher = async () => {
    callCount += 1;
    return jsonResponse(searchPayload);
  };

  await assert.rejects(
    integration.searchAndAnalyze(
      { address: "부산", plannedDeposit: 200000000 },
      { fetcher: searchFetcher },
    ),
    (error) => {
      assert.ok(error instanceof integration.ApiError);
      assert.equal(error.code, "PROPERTY_SELECTION_REQUIRED");
      assert.equal(error.details.length, 2);
      return true;
    },
  );
  assert.equal(callCount, 1, "selection 전에는 /analyze를 호출하지 않아야 합니다");

  const items = integration.adaptPropertySearchResponse(searchPayload);
  let analyzeBody;
  const selectedResult = await integration.analyzeSelectedProperty(
    items[1],
    {
      address: "부산",
      plannedDeposit: 200000000,
      userNote: "선택한 매물만 분석",
    },
    {
      baseUrl: "https://api.example.com",
      fetcher: async (_input, init) => {
        analyzeBody = JSON.parse(init.body);
        return jsonResponse({
          ...analyzeResponse,
          property_summary: {
            ...analyzeResponse.property_summary,
            property_id: "P002",
            guarantee_product_type: "rental_deposit",
          },
        });
      },
    },
  );

  assert.equal(selectedResult.propertyId, "P002");
  assert.equal(analyzeBody.property_id, "P002");
  assert.equal(analyzeBody.guarantee_product_type, "rental_deposit");
});

test("does not call analyze or fabricate fallback data when search is empty", async () => {
  let callCount = 0;
  const fetcher = async () => {
    callCount += 1;
    return jsonResponse({ items: [] });
  };

  await assert.rejects(
    integration.searchAndAnalyze(
      { address: "검색되지 않는 주소", plannedDeposit: 100000000 },
      { fetcher },
    ),
    (error) => {
      assert.ok(error instanceof integration.ApiError);
      assert.equal(error.code, "PROPERTY_NOT_FOUND");
      assert.equal(error.status, 404);
      return true;
    },
  );
  assert.equal(callCount, 1);
});

test("preserves every documented AI API status and message", () => {
  const statuses = [
    "ok",
    "fallback",
    "disabled",
    "unavailable",
    "timeout",
    "error",
    "local_mock",
    "unsupported_product_type",
  ];

  for (const status of statuses) {
    const mapped = integration.adaptAnalyzeResponse({
      ai_api_status: status,
      ai_api_message: `${status} message`,
      property_summary: { property_id: "P-AI" },
    });
    assert.equal(mapped.aiApiStatus, status);
    assert.equal(mapped.aiApiMessage, `${status} message`);
  }

  const unknown = integration.adaptAnalyzeResponse({
    ai_api_status: "future_status",
    property_summary: { property_id: "P-AI" },
  });
  assert.equal(unknown.aiApiStatus, "unknown");
  assert.equal(unknown.aiApiMessage, null);
});

test("maps incomplete API responses to explicit empty values", () => {
  const mapped = integration.adaptAnalyzeResponse({
    property_summary: { property_id: "P-EMPTY" },
    generated_at: "2026-07-25T12:00:00Z",
  });

  assert.equal(mapped.propertySummary.propertyId, "P-EMPTY");
  assert.equal(mapped.propertySummary.referenceValue, null);
  assert.ok(
    mapped.propertySummary.fields.every((field) => field.referenceDate === null),
  );
  assert.equal(mapped.guarantee.status, null);
  assert.equal(mapped.riskAnalysis.analysisConfidence, null);
  assert.deepEqual(mapped.riskAnalysis.signals, []);
  assert.deepEqual(mapped.checklist, []);
  assert.deepEqual(mapped.similarCases, []);
  assert.equal(mapped.aiApiStatus, "unknown");
  assert.equal(mapped.aiApiMessage, null);
});

test("keeps the UI wired to live integration without sample data imports", async () => {
  const [page, property, guarantee, risk, similar] = await Promise.all([
    readFile(new URL("app/page.tsx", frontendRootUrl), "utf8"),
    readFile(
      new URL("app/components/PropertySummary.tsx", frontendRootUrl),
      "utf8",
    ),
    readFile(
      new URL("app/components/GuaranteeStatusCard.tsx", frontendRootUrl),
      "utf8",
    ),
    readFile(
      new URL("app/components/RiskAnalysis.tsx", frontendRootUrl),
      "utf8",
    ),
    readFile(
      new URL("app/components/SimilarCaseCard.tsx", frontendRootUrl),
      "utf8",
    ),
  ]);

  assert.match(page, /searchProperties/);
  assert.match(page, /analyzeSelectedProperty/);
  assert.match(page, /handleAnalyzeSelected/);
  assert.doesNotMatch(page, /searchItems\[0\]/);
  assert.match(page, /<ActionChecklist/);
  assert.match(similar, /AI 유사사례 서비스에 현재 연결되지 않았습니다/);
  assert.match(similar, /로컬 모의 유사사례/);
  assert.match(risk, /확정 위험/);
  assert.match(risk, /확인 필요/);
  assert.match(risk, /분석 신뢰도/);
  assert.doesNotMatch(risk, /riskScore|risk_score|참고 위험신호 점수|risk-score/);
  assert.doesNotMatch(risk, /\/\s*100/);
  assert.doesNotMatch(
    property,
    /source-guide|<dt>출처|<dt>기준일|분석 생성 시각|generatedAt|formatDate/,
  );
  assert.doesNotMatch(page, /권리정보와 응답 출처/);
  for (const source of [page, property, guarantee, risk, similar]) {
    assert.doesNotMatch(source, /(?:\/data\/|Sample|sample)/);
  }

  await assert.rejects(
    access(new URL("app/data", frontendRootUrl)),
    (error) => error?.code === "ENOENT",
  );
});

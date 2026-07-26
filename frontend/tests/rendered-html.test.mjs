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
  guarantee_branch: "eligible",
  guarantee_message: "반환보증 가입 가능성을 확인했습니다.",
  guarantee_disclaimer: "가입 완료 여부는 보증기관에서 다시 확인해 주세요.",
  risk_stage: "caution",
  risk_score: 42,
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
    guarantee_status: "eligible",
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

test("uses the configured API base URL and trims trailing slashes", () => {
  const previous = process.env.NEXT_PUBLIC_API_BASE_URL;

  try {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:9000///";
    assert.equal(
      integration.getApiBaseUrl(),
      "http://127.0.0.1:9000",
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

test("searches by address, selects the first property, then posts analyze", async () => {
  const calls = [];
  const fetcher = async (input, init) => {
    calls.push({ input: String(input), init });

    if (calls.length === 1) {
      return jsonResponse({
        items: [
          {
            property_id: "P001",
            address_display: "부산광역시 수영구 광안동 1-1",
            district: "수영구",
            housing_type: "apartment",
            reference_value: 350000000,
            guarantee_status: "eligible",
          },
          {
            property_id: "P002",
            address_display: "두 번째 매물",
          },
        ],
      });
    }

    return jsonResponse(analyzeResponse);
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
    user_note: "잔금일에 근저당을 말소한다고 들었습니다.",
  });

  assert.equal(result.propertyId, "P001");
  assert.equal(result.analysis.propertySummary.propertyId, "P001");
  assert.equal(result.analysis.guarantee.rawStatus, "eligible");
  assert.equal(result.analysis.guarantee.branch, "eligible");
  assert.equal(result.analysis.guarantee.propertyStatus, "eligible");
  assert.equal(result.analysis.guarantee.status, "estimated_eligible");
  assert.equal(result.analysis.guarantee.group, "check_required");
  assert.equal(result.analysis.riskAnalysis.riskStage, "caution");
  assert.equal(result.analysis.riskAnalysis.riskScore, 42);
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
});

test("falls back to address-only analysis when property search is empty", async () => {
  const calls = [];
  const fetcher = async (input, init) => {
    calls.push({ input: String(input), init });
    if (calls.length === 1) return jsonResponse({ items: [] });
    return jsonResponse({
      ...analyzeResponse,
      property_summary: {
        ...analyzeResponse.property_summary,
        property_id: "ADDR-abc123",
        address_display: "서울특별시 강남구 테헤란로 152",
      },
    });
  };

  const result = await integration.searchAndAnalyze(
    { address: "서울특별시 강남구 테헤란로 152", plannedDeposit: 100000000 },
    { fetcher },
  );

  assert.equal(calls.length, 2);
  assert.equal(calls[1].init.method, "POST");
  assert.deepEqual(JSON.parse(calls[1].init.body), {
    address_query: "서울특별시 강남구 테헤란로 152",
    planned_deposit: 100000000,
    monthly_rent: 0,
    user_note: "",
  });
  assert.equal(result.propertyId, "ADDR-abc123");
  assert.equal(result.searchItem.propertyId, "ADDR-abc123");
  assert.equal(
    result.analysis.propertySummary.addressDisplay,
    "서울특별시 강남구 테헤란로 152",
  );
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
  assert.equal(mapped.riskAnalysis.riskScore, null);
  assert.deepEqual(mapped.riskAnalysis.signals, []);
  assert.deepEqual(mapped.checklist, []);
  assert.deepEqual(mapped.similarCases, []);
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

  assert.match(page, /searchAndAnalyze/);
  assert.match(page, /<ActionChecklist/);
  for (const source of [page, property, guarantee, risk, similar]) {
    assert.doesNotMatch(source, /(?:\/data\/|Sample|sample)/);
  }

  await assert.rejects(
    access(new URL("app/data", frontendRootUrl)),
    (error) => error?.code === "ENOENT",
  );
});

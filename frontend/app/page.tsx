"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ActionChecklist } from "./components/ActionChecklist";
import { GuaranteeStatusCard } from "./components/GuaranteeStatusCard";
import { PropertySummary } from "./components/PropertySummary";
import { RiskAnalysis } from "./components/RiskAnalysis";
import { SimilarCaseCard } from "./components/SimilarCaseCard";
import {
  analyzeSelectedProperty,
  ApiError,
  searchProperties,
  type ChecklistItemViewModel,
  type PropertySearchItem,
  type RecommendedActionViewModel,
  type SearchAndAnalyzeInput,
  type SearchAndAnalyzeResult,
} from "./integration";

type RequestStage = "idle" | "searching" | "selecting" | "analyzing";

function formatWon(value: string | number) {
  const amount =
    typeof value === "number" ? value : Number(value.replaceAll(",", ""));
  return Number.isFinite(amount) && amount > 0
    ? new Intl.NumberFormat("ko-KR").format(amount)
    : "";
}

function housingTypeLabel(value: string | null) {
  const labels: Record<string, string> = {
    apartment: "아파트",
    multi_unit: "다세대주택",
    multi_household: "다가구주택",
    officetel: "오피스텔",
    row_house: "연립주택",
  };
  return value ? (labels[value] ?? value) : "주택유형 미제공";
}

function guaranteeStatusLabel(value: string | null) {
  const labels: Record<string, string> = {
    estimated_eligible: "가입 가능성 추정",
    officially_eligible: "공식 가입 가능",
    applied: "가입 신청",
    enrolled: "가입 완료",
    ineligible: "가입 불가",
    unknown: "확인 필요",
  };
  return value ? (labels[value] ?? value) : "보증 상태 미제공";
}

function guaranteeProductLabel(value: PropertySearchItem["guaranteeProductType"]) {
  if (value === "jeonse_return") return "전세보증금 반환보증";
  if (value === "rental_deposit") return "임대보증금 보증";
  return "보증상품 확인 필요";
}

function toErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.code === "NETWORK_ERROR") {
      return "백엔드 API에 연결하지 못했습니다. 서버 실행 상태와 API 주소, CORS 설정을 확인해 주세요.";
    }
    return error.message;
  }

  return "분석 요청 중 예상하지 못한 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.";
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

function toChecklistItems(items: ChecklistItemViewModel[]) {
  return items.map((item, index) => ({
    code: item.code ?? `CHECK_${index + 1}`,
    title: item.title ?? "제목이 제공되지 않은 확인 항목",
    description:
      item.description ?? "API 응답에 이 항목의 세부 설명이 없습니다.",
    priority: item.priority ?? "default",
  }));
}

function toRecommendedAction(action: RecommendedActionViewModel | null) {
  if (!action || (!action.label && !action.description)) return null;

  return {
    label: action.label ?? "권장 행동",
    description:
      action.description ?? "API 응답에 권장 행동의 세부 설명이 없습니다.",
  };
}

export default function Home() {
  const [address, setAddress] = useState("");
  const [deposit, setDeposit] = useState("200000000");
  const [situation, setSituation] = useState("");
  const [result, setResult] = useState<SearchAndAnalyzeResult | null>(null);
  const [requestStage, setRequestStage] = useState<RequestStage>("idle");
  const [searchResults, setSearchResults] = useState<PropertySearchItem[]>([]);
  const [selectedPropertyId, setSelectedPropertyId] = useState<string | null>(
    null,
  );
  const [pendingInput, setPendingInput] =
    useState<SearchAndAnalyzeInput | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isLoading =
    requestStage === "searching" || requestStage === "analyzing";

  function invalidateAnalysis() {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setRequestStage("idle");
    setSearchResults([]);
    setSelectedPropertyId(null);
    setPendingInput(null);
    setResult(null);
    setErrorMessage(null);
  }

  async function runAnalysis(
    searchItem: PropertySearchItem,
    input: SearchAndAnalyzeInput,
    returnToSelection: boolean,
  ) {
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    setRequestStage("analyzing");
    setResult(null);
    setErrorMessage(null);

    try {
      const nextResult = await analyzeSelectedProperty(searchItem, input, {
        signal: controller.signal,
      });
      if (abortControllerRef.current !== controller) return;

      setResult(nextResult);
      setSearchResults([]);
      setSelectedPropertyId(null);
      setPendingInput(null);
      setRequestStage("idle");
    } catch (error) {
      if (
        abortControllerRef.current === controller &&
        !isAbortError(error)
      ) {
        setErrorMessage(toErrorMessage(error));
        setRequestStage(returnToSelection ? "selecting" : "idle");
      }
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const plannedDeposit = Number(deposit);
    if (!Number.isFinite(plannedDeposit) || plannedDeposit <= 0) {
      setErrorMessage("0원보다 큰 계약 예정 보증금을 입력해 주세요.");
      return;
    }

    const input: SearchAndAnalyzeInput = {
      address: address.trim(),
      plannedDeposit,
      monthlyRent: 0,
      userNote: situation,
    };
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    setRequestStage("searching");
    setResult(null);
    setSearchResults([]);
    setSelectedPropertyId(null);
    setPendingInput(input);
    setErrorMessage(null);

    try {
      const items = await searchProperties(input.address, {
        signal: controller.signal,
      });
      if (abortControllerRef.current !== controller) return;

      if (items.length === 0) {
        throw new ApiError("주소와 일치하는 매물을 찾지 못했습니다.", {
          status: 404,
          code: "PROPERTY_NOT_FOUND",
        });
      }

      if (items.length === 1) {
        abortControllerRef.current = null;
        await runAnalysis(items[0], input, false);
        return;
      }

      setSearchResults(items);
      setSelectedPropertyId(null);
      setRequestStage("selecting");
      abortControllerRef.current = null;
    } catch (error) {
      if (
        abortControllerRef.current === controller &&
        !isAbortError(error)
      ) {
        setErrorMessage(toErrorMessage(error));
        setRequestStage("idle");
        abortControllerRef.current = null;
      }
    }
  }

  async function handleAnalyzeSelected() {
    const selected = searchResults.find(
      (item) => item.propertyId === selectedPropertyId,
    );
    if (!selected || !pendingInput) {
      setErrorMessage("분석할 매물을 하나 선택해 주세요.");
      return;
    }

    await runAnalysis(selected, pendingInput, true);
  }

  useEffect(
    () => () => {
      abortControllerRef.current?.abort();
    },
    [],
  );

  useEffect(() => {
    if (result) {
      document
        .getElementById("property-summary")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [result]);

  const checklist = result
    ? toChecklistItems(result.analysis.checklist)
    : [];
  const recommendedAction = result
    ? toRecommendedAction(result.analysis.riskAnalysis.recommendedAction)
    : null;

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#" aria-label="안심계약 레이더 홈">
          <span className="brand-mark" aria-hidden="true">
            A
          </span>
          <span>안심계약 레이더</span>
        </a>
        <span className="prototype-badge">DIVE 2026</span>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">계약 전에 한 번 더 확인하세요</p>
          <h1>
            주소와 보증금으로 시작하는
            <br />
            <span>전세계약 위험 확인</span>
          </h1>
          <p className="hero-description">
            실제 계약 주소를 검색해 매물 정보를 찾고, 반환보증 상태와 위험
            신호를 백엔드 분석 결과 그대로 정리합니다. 확인된 사실과 아직
            확인해야 할 내용을 구분해 보여드립니다.
          </p>
        </div>

        <div className="search-card">
          <div className="card-heading">
            <div>
              <p className="step-label">STEP 01</p>
              <h2>계약할 매물을 알려주세요</h2>
            </div>
          </div>

          <form onSubmit={handleSubmit} aria-busy={isLoading}>
            <label htmlFor="address">계약할 주택의 실제 주소</label>
            <input
              id="address"
              type="text"
              value={address}
              onChange={(event) => {
                setAddress(event.target.value);
                invalidateAnalysis();
              }}
              placeholder="도로명 주소 또는 지번 주소를 입력하세요"
              autoComplete="street-address"
              minLength={2}
              disabled={isLoading}
              required
            />
            <p className="field-help">
              한 건이면 바로 분석하고, 여러 건이면 계약할 매물을 직접
              선택합니다.
            </p>

            <label htmlFor="deposit">계약 예정 보증금</label>
            <div className="money-input">
              <input
                id="deposit"
                inputMode="numeric"
                value={formatWon(deposit)}
                onChange={(event) => {
                  setDeposit(event.target.value.replaceAll(/[^0-9]/g, ""));
                  invalidateAnalysis();
                }}
                placeholder="예: 200,000,000"
                disabled={isLoading}
                required
              />
              <span>원</span>
            </div>

            <label htmlFor="situation">
              상황 설명 <small>선택</small>
            </label>
            <textarea
              id="situation"
              value={situation}
              onChange={(event) => {
                setSituation(event.target.value);
                invalidateAnalysis();
              }}
              placeholder="예: 집주인이 잔금일에 근저당을 말소한다고 했습니다."
              rows={3}
              disabled={isLoading}
            />

            <button
              className="primary-button"
              type="submit"
              disabled={isLoading}
            >
              {requestStage === "searching"
                ? "매물 검색 중"
                : requestStage === "analyzing"
                  ? "위험 분석 중"
                  : "매물정보 확인하기"}
              <span aria-hidden="true">{isLoading ? "…" : "→"}</span>
            </button>
          </form>

          {requestStage === "selecting" ? (
            <fieldset className="property-search-results">
              <legend>검색 결과 {searchResults.length}건</legend>
              <p>실제로 계약할 매물을 선택한 뒤 분석을 시작해 주세요.</p>
              <div className="property-choice-list">
                {searchResults.map((item) => {
                  const isSelected = selectedPropertyId === item.propertyId;

                  return (
                    <label
                      className={`property-choice${isSelected ? " is-selected" : ""}`}
                      key={item.propertyId}
                    >
                      <input
                        type="radio"
                        name="selected-property"
                        value={item.propertyId}
                        checked={isSelected}
                        onChange={() => {
                          setSelectedPropertyId(item.propertyId);
                          setErrorMessage(null);
                        }}
                      />
                      <span className="property-choice-body">
                        <strong>
                          {item.addressDisplay ?? "주소 정보가 없는 매물"}
                        </strong>
                        <span>
                          {item.district ?? "지역 미제공"} ·{" "}
                          {housingTypeLabel(item.housingType)}
                        </span>
                        <span>
                          참고가액{" "}
                          {item.referenceValue === null
                            ? "미제공"
                            : `${formatWon(item.referenceValue)}원`}
                        </span>
                        <small>
                          {guaranteeStatusLabel(item.guaranteeStatus)} ·{" "}
                          {guaranteeProductLabel(item.guaranteeProductType)} ·{" "}
                          {item.propertyId}
                        </small>
                      </span>
                    </label>
                  );
                })}
              </div>
              <button
                type="button"
                className="primary-button property-analyze-button"
                disabled={!selectedPropertyId}
                onClick={handleAnalyzeSelected}
              >
                선택한 매물 분석하기
                <span aria-hidden="true">→</span>
              </button>
            </fieldset>
          ) : null}

          {isLoading ? (
            <p className="api-progress" role="status" aria-live="polite">
              {requestStage === "searching"
                ? "입력한 주소와 일치하는 매물을 찾고 있습니다."
                : "선택한 매물의 보증 상태와 위험 신호를 분석하고 있습니다."}
            </p>
          ) : null}

          {errorMessage ? (
            <div className="api-error" role="alert">
              <strong>요청을 완료하지 못했습니다.</strong>
              <span>{errorMessage}</span>
            </div>
          ) : null}

          <p className="privacy-note">
            입력한 주소와 상황 설명은 매물 검색 및 분석을 위해 백엔드 API로
            전송됩니다.
          </p>
        </div>
      </section>

      {result ? (
        <>
          <PropertySummary
            property={result.analysis.propertySummary}
            searchItem={result.searchItem}
            searchedAddress={address}
            plannedDeposit={Number(deposit)}
            generatedAt={result.analysis.generatedAt}
            onEdit={() => {
              invalidateAnalysis();
              document
                .getElementById("address")
                ?.scrollIntoView({ behavior: "smooth", block: "center" });
            }}
          />
          <GuaranteeStatusCard
            guarantee={result.analysis.guarantee}
            generatedAt={result.analysis.generatedAt}
          />
          <RiskAnalysis analysis={result.analysis.riskAnalysis} />
          <SimilarCaseCard
            cases={result.analysis.similarCases}
            generatedAt={result.analysis.generatedAt}
            aiApiStatus={result.analysis.aiApiStatus}
            aiApiMessage={result.analysis.aiApiMessage}
          />
          <ActionChecklist
            checklist={checklist}
            recommendedAction={recommendedAction}
            resetKey={`${result.propertyId}:${result.analysis.generatedAt ?? ""}`}
          />
        </>
      ) : null}

      <section className="flow-section" aria-labelledby="flow-title">
        <div>
          <p className="eyebrow">분석 흐름</p>
          <h2 id="flow-title">실제 API 응답을 여섯 단계로 정리합니다</h2>
        </div>
        <ol className="flow-list">
          <li>
            <span>01</span>
            <strong>주소 검색</strong>
            <p>실제 주소 검색 결과에서 분석할 매물 ID를 찾습니다.</p>
          </li>
          <li>
            <span>02</span>
            <strong>매물정보 확인</strong>
            <p>주택유형, 참고가액, 권리정보와 응답 출처를 확인합니다.</p>
          </li>
          <li>
            <span>03</span>
            <strong>반환보증 상태</strong>
            <p>가입 가능성과 실제 가입 완료를 구분해 안내합니다.</p>
          </li>
          <li>
            <span>04</span>
            <strong>위험·미확인 분리</strong>
            <p>확인된 위험을 아직 모르는 정보와 섞지 않습니다.</p>
          </li>
          <li>
            <span>05</span>
            <strong>유사사례 설명</strong>
            <p>AI 연결 상태와 반환된 상담사례를 구분해 보여줍니다.</p>
          </li>
          <li>
            <span>06</span>
            <strong>행동 체크리스트</strong>
            <p>분석 결과에 따라 계약 전에 확인할 일을 정리합니다.</p>
          </li>
        </ol>
      </section>

      <footer>
        <strong>안심계약 레이더</strong>
        <p>
          본 서비스는 계약 전 의사결정을 돕는 참고 도구이며 법률적 확정
          판단이나 계약의 안전을 보장하지 않습니다.
        </p>
      </footer>
    </main>
  );
}

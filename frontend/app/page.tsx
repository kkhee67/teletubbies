"use client";

import { useEffect, useRef, useState } from "react";
import { ActionChecklist } from "./components/ActionChecklist";
import { GuaranteeStatusCard } from "./components/GuaranteeStatusCard";
import { PropertySummary } from "./components/PropertySummary";
import { RiskAnalysis } from "./components/RiskAnalysis";
import { SimilarCaseCard } from "./components/SimilarCaseCard";
import {
  ApiError,
  searchAndAnalyze,
  type ChecklistItemViewModel,
  type RecommendedActionViewModel,
  type SearchAndAnalyzeResult,
} from "./integration";

const POSTCODE_SCRIPT_ID = "daum-postcode-script";
const POSTCODE_SCRIPT_URL =
  "https://t1.daumcdn.net/mapjsapi/bundle/postcode/prod/postcode.v2.js";

type PostcodeResult = {
  address?: string;
  roadAddress?: string;
  jibunAddress?: string;
};

declare global {
  interface Window {
    daum?: {
      Postcode: new (options: {
        oncomplete: (data: PostcodeResult) => void;
      }) => {
        open: (options?: { q?: string }) => void;
      };
    };
  }
}

function formatWon(value: string | number) {
  const amount =
    typeof value === "number" ? value : Number(value.replaceAll(",", ""));
  return Number.isFinite(amount) && amount > 0
    ? new Intl.NumberFormat("ko-KR").format(amount)
    : "";
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

function loadPostcodeScript() {
  if (typeof window === "undefined") return Promise.reject();
  if (window.daum?.Postcode) return Promise.resolve();

  return new Promise<void>((resolve, reject) => {
    const existingScript = document.getElementById(POSTCODE_SCRIPT_ID);
    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(), { once: true });
      existingScript.addEventListener("error", () => reject(), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.id = POSTCODE_SCRIPT_ID;
    script.src = POSTCODE_SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject();
    document.head.appendChild(script);
  });
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
  const [isLoading, setIsLoading] = useState(false);
  const [isAddressLookupLoading, setIsAddressLookupLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  function invalidateAnalysis() {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsLoading(false);
    setResult(null);
    setErrorMessage(null);
  }

  async function handleOpenAddressSearch() {
    setErrorMessage(null);
    setIsAddressLookupLoading(true);

    try {
      await loadPostcodeScript();
      const Postcode = window.daum?.Postcode;
      if (!Postcode) throw new Error("Postcode API unavailable");

      new Postcode({
        oncomplete(data) {
          const selectedAddress =
            data.roadAddress || data.jibunAddress || data.address || "";
          if (selectedAddress) {
            setAddress(selectedAddress);
            invalidateAnalysis();
          }
        },
      }).open({ q: address.trim() || undefined });
    } catch {
      setErrorMessage(
        "주소 검색창을 열지 못했습니다. 주소를 직접 입력해서 계속 진행할 수 있습니다.",
      );
    } finally {
      setIsAddressLookupLoading(false);
    }
  }

  async function handleAnalyze() {
    const plannedDeposit = Number(deposit);
    if (!Number.isFinite(plannedDeposit) || plannedDeposit <= 0) {
      setErrorMessage("0원보다 큰 계약 예정 보증금을 입력해 주세요.");
      return;
    }

    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    setIsLoading(true);
    setResult(null);
    setErrorMessage(null);

    try {
      const nextResult = await searchAndAnalyze(
        {
          address,
          plannedDeposit,
          monthlyRent: 0,
          userNote: situation,
        },
        { signal: controller.signal },
      );
      setResult(nextResult);
    } catch (error) {
      if (!isAbortError(error)) {
        setErrorMessage(toErrorMessage(error));
      }
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
        setIsLoading(false);
      }
    }
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

          <div className="analysis-form" role="form" aria-busy={isLoading}>
            <label htmlFor="address">계약할 주택의 실제 주소</label>
            <div className="address-input-row">
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
              <button
                className="address-search-button"
                type="button"
                onClick={handleOpenAddressSearch}
                disabled={isLoading || isAddressLookupLoading}
              >
                {isAddressLookupLoading ? "검색 준비 중" : "주소 검색"}
              </button>
            </div>
            <p className="field-help">
              등록된 매물이 없으면 입력한 주소만으로 임시 분석을 진행합니다.
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
              type="button"
              onClick={handleAnalyze}
              disabled={isLoading}
            >
              {isLoading ? "매물 검색·분석 중" : "매물정보 확인하기"}
              <span aria-hidden="true">{isLoading ? "…" : "→"}</span>
            </button>
          </div>

          {isLoading ? (
            <p className="api-progress" role="status" aria-live="polite">
              주소 검색 후 분석 API 응답을 기다리고 있습니다.
            </p>
          ) : null}

          {errorMessage ? (
            <div className="api-error" role="alert">
              <strong>분석을 완료하지 못했습니다.</strong>
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
              setResult(null);
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
            <p>API가 찾은 상담사례와 놓친 확인 항목을 보여줍니다.</p>
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

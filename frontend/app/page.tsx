"use client";

import { FormEvent, useEffect, useState } from "react";
import { GuaranteeStatusCard } from "./components/GuaranteeStatusCard";
import { PropertySummary } from "./components/PropertySummary";
import { RiskAnalysis } from "./components/RiskAnalysis";
import type { GuaranteeStatus } from "./data/guaranteeStates";

function formatWon(value: string) {
  const amount = Number(value.replaceAll(",", ""));
  return amount ? new Intl.NumberFormat("ko-KR").format(amount) : "";
}

export default function Home() {
  const [address, setAddress] = useState("");
  const [deposit, setDeposit] = useState("200000000");
  const [situation, setSituation] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [guaranteeStatus, setGuaranteeStatus] =
    useState<GuaranteeStatus>("ineligible");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
  }

  useEffect(() => {
    if (submitted) {
      document
        .getElementById("property-summary")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [submitted]);

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#" aria-label="안심계약 레이더 홈">
          <span className="brand-mark" aria-hidden="true">A</span>
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
            어려운 부동산 정보를 처음부터 모두 입력할 필요가 없습니다.
            매물 정보와 반환보증 상태를 먼저 정리하고, 확인된 위험과 아직
            확인해야 할 내용을 나누어 알려드립니다.
          </p>
        </div>

        <div className="search-card">
          <div className="card-heading">
            <div>
              <p className="step-label">STEP 01</p>
              <h2>계약할 매물을 알려주세요</h2>
            </div>
          </div>

          <form onSubmit={handleSubmit}>
            <label htmlFor="address">계약할 주택 주소</label>
            <input
              id="address"
              type="text"
              value={address}
              onChange={(event) => {
                setAddress(event.target.value);
                setSubmitted(false);
              }}
              placeholder="도로명 주소 또는 지번 주소를 입력하세요"
              autoComplete="street-address"
              minLength={5}
              required
            />
            <p className="field-help">
              다른 팀원의 주소 검색 API와 연결할 입력 항목입니다.
            </p>

            <label htmlFor="deposit">계약 예정 보증금</label>
            <div className="money-input">
              <input
                id="deposit"
                inputMode="numeric"
                value={formatWon(deposit)}
                onChange={(event) => {
                  setDeposit(event.target.value.replaceAll(/[^0-9]/g, ""));
                  setSubmitted(false);
                }}
                placeholder="예: 200,000,000"
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
              onChange={(event) => setSituation(event.target.value)}
              placeholder="예: 집주인이 잔금일에 근저당을 말소한다고 했습니다."
              rows={3}
            />

            <button className="primary-button" type="submit">
              매물정보 확인하기
              <span aria-hidden="true">→</span>
            </button>
          </form>

          <p className="privacy-note">
            상세주소는 검색에만 사용하며 분석 결과와 로그에는 축약된 주소를
            사용합니다.
          </p>
        </div>
      </section>

      {submitted && address.trim() && (
        <>
          <PropertySummary
            address={address}
            deposit={formatWon(deposit)}
            onEdit={() => {
              setSubmitted(false);
              document
                .getElementById("address")
                ?.scrollIntoView({ behavior: "smooth", block: "center" });
            }}
          />
          <GuaranteeStatusCard
            selectedStatus={guaranteeStatus}
            onStatusChange={setGuaranteeStatus}
          />
          <RiskAnalysis guaranteeStatus={guaranteeStatus} />
        </>
      )}

      <section className="flow-section" aria-labelledby="flow-title">
        <div>
          <p className="eyebrow">분석 흐름</p>
          <h2 id="flow-title">복잡한 계약 정보를 네 단계로 정리합니다</h2>
        </div>
        <ol className="flow-list">
          <li>
            <span>01</span>
            <strong>매물정보 확인</strong>
            <p>주택유형, 참고가액, 권리정보와 각각의 출처를 확인합니다.</p>
          </li>
          <li>
            <span>02</span>
            <strong>반환보증 상태</strong>
            <p>가입 가능성과 실제 가입 완료를 구분해 안내합니다.</p>
          </li>
          <li>
            <span>03</span>
            <strong>위험과 미확인 분리</strong>
            <p>확인된 위험을 아직 모르는 정보와 섞지 않습니다.</p>
          </li>
          <li>
            <span>04</span>
            <strong>행동 안내</strong>
            <p>계약 전에 확인하거나 협상할 일을 쉬운 말로 제시합니다.</p>
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

# 안심계약 레이더

주소와 계약 예정 보증금으로 시작해 반환보증 상태, 확인된 위험신호,
확인이 필요한 정보와 분석 신뢰도를 구분해 보여주는 계약 전 의사결정
지원 서비스입니다.

## 현재 구현된 기능

- 실제 주소 입력을 위한 입력 화면
- 계약 예정 보증금과 선택형 상황 설명
- 매물정보 확인 화면
  - 주택유형
  - 참고 주택가액
  - 근저당
  - 압류·가압류
  - 공동담보
  - 항목별 출처와 기준일
- 반환보증 상태 6단계
  - `estimated_eligible`
  - `officially_eligible`
  - `applied`
  - `enrolled`
  - `ineligible`
  - `unknown`
- 반환보증 화면 그룹 4개
  - 확인 필요
  - 가입 절차 진행
  - 보호장치 확보
  - 심층분석 필요
- 분석 결과 화면
  - 위험단계
  - 확인된 위험신호
  - 확인이 필요한 정보
  - 분석 신뢰도

현재 데이터는 API 연결 전 개발용 샘플이며, 데이터 파일을 실제 팀 API
응답으로 교체할 수 있도록 화면과 분리되어 있습니다.

## 실행 방법

Node.js 22.13 이상이 필요합니다.

```bash
pnpm install
pnpm run dev
```

브라우저에서 터미널에 표시된 로컬 주소로 접속합니다.

## 빌드 확인

```bash
pnpm run build
```

## 주요 파일

```text
app/
├─ components/
│  ├─ PropertySummary.tsx
│  ├─ GuaranteeStatusCard.tsx
│  └─ RiskAnalysis.tsx
├─ data/
│  ├─ propertySample.ts
│  ├─ guaranteeStates.ts
│  └─ analysisSample.ts
├─ globals.css
├─ layout.tsx
└─ page.tsx
```

## 통합 원칙

- 가입 가능과 가입 완료를 구분합니다.
- `enrolled` 상태에서만 보호장치 확보로 표현합니다.
- 확인된 위험과 미확인 정보를 서로 다른 목록으로 표시합니다.
- 분석 신뢰도는 계약 안전도가 아니라 정보 확인 정도입니다.
- 실제 계약에서는 최신 공식 서류와 반환보증 가입 여부를 다시
  확인해야 합니다.

# 안심계약 레이더

주소와 계약 예정 보증금을 바탕으로 반환보증 상태, 위험 신호와 계약 전
확인 사항을 보여주는 프론트엔드입니다. 화면은 개발용 샘플 데이터가 아닌
백엔드 분석 API 응답을 기준으로 렌더링합니다.

## 백엔드 연결 흐름

사용자가 주소를 입력하고 제출하면 다음 요청을 순서대로 보냅니다.

1. `GET /properties/search?q={주소}`로 매물을 검색합니다.
2. 검색 결과의 첫 번째 `property_id`를 가져옵니다.
3. 해당 `property_id`, 입력 주소, 보증금, 월세와 사용자 메모를 담아
   `POST /analyze`를 호출합니다.
4. 분석 응답을 매물 요약, 반환보증 상태, 위험 분석, 유사 사례와 행동
   체크리스트 화면에 표시합니다.

분석 요청 예시는 다음과 같습니다.

```json
{
  "property_id": "P001",
  "address_query": "수영구",
  "planned_deposit": 200000000,
  "monthly_rent": 0,
  "user_note": "잔금일에 근저당을 말소한다고 들었습니다."
}
```

검색 결과가 없거나 네트워크·서버 응답에 문제가 있으면 샘플로 대체하지
않고 사용자에게 오류 상태를 표시합니다.

## 환경 변수

`.env.example`을 `.env.local`로 복사한 뒤 백엔드 주소를 환경에 맞게
설정합니다.

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

환경 변수가 없으면 `http://127.0.0.1:8000`을 기본값으로 사용합니다.
배포 환경에서는 브라우저가 접근 가능한 백엔드 URL과 해당 도메인을
허용하는 백엔드 CORS 설정이 필요합니다.

## 실행 방법

Node.js 22.13 이상이 필요합니다. 백엔드를 먼저 실행한 다음 프론트엔드를
실행합니다.

```bash
pnpm install
pnpm run dev
```

브라우저에서 터미널에 표시된 로컬 주소로 접속합니다.

## 검증

```bash
pnpm run test
pnpm run lint
```

`test` 명령은 프로덕션 빌드와 서버 렌더링, API 호출 및 응답 변환에 대한
회귀 검사를 수행합니다.

## 주요 파일

```text
app/
├─ components/
│  ├─ ActionChecklist.tsx
│  ├─ PropertySummary.tsx
│  ├─ GuaranteeStatusCard.tsx
│  ├─ RiskAnalysis.tsx
│  └─ SimilarCaseCard.tsx
├─ integration/
│  ├─ api.ts
│  ├─ adapters.ts
│  └─ types.ts
├─ globals.css
├─ layout.tsx
└─ page.tsx
```

## 통합 원칙

- `property_summary`는 매물 요약 화면에 표시합니다.
- `guarantee_branch`, `guarantee_message`,
  `property_summary.guarantee_status`는 반환보증 상태 화면에 표시합니다.
- `risk_stage`, `risk_score`, `signals`, `checklist`,
  `recommended_action`은 위험 분석과 행동 체크리스트에 표시합니다.
- 가입 가능과 실제 가입 완료를 구분하며, 실제 가입 완료가 확인된 경우에만
  보호장치가 확보되었다고 표현합니다.
- 위험 점수는 피해 확률이나 계약 안전 보증이 아닙니다.
- 실제 계약에서는 최신 공식 서류와 반환보증 가입 여부를 다시 확인해야
  합니다.

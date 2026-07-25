# 안심계약 레이더 백엔드

주소 기반 MVP를 위한 FastAPI 서버입니다. 프론트가 주소를 검색하고 매물을 선택하면, 보증금 입력값을 바탕으로 반환보증 분기, 위험신호, 유사 상담사례, 쉬운 설명, 체크리스트를 하나의 JSON으로 반환합니다.

## 실행

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r ..\requirements.txt
fastapi dev main.py
```

`fastapi` 명령이 안 되면:

```bash
python -m uvicorn main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## 주요 API

```text
GET  /health
GET  /properties/search?q=수영구
GET  /properties/P001
POST /analyze
POST /simulate
```

## AI API 연동

`/analyze`는 먼저 AI API의 `/api/similar-cases`를 호출해 유사 상담사례와 쉬운 설명을 가져옵니다.

- 기본 AI API 주소는 `http://127.0.0.1:8001`입니다.
- 다른 주소를 쓰려면 `AI_API_BASE_URL` 환경변수를 설정하세요.
- 응답 대기시간 기본값은 0.5초이며 `AI_API_TIMEOUT_SECONDS`로 조정할 수 있습니다.
- AI API가 꺼져 있거나 오류를 반환하면 기존 로컬 모의 유사사례로 폴백하고 `ai_api_status: "fallback"`을 반환합니다.
- `guarantee_product_type`으로 `jeonse_return`, `rental_deposit`, `unknown`을 전달할 수 있습니다.

AI API는 별도 터미널에서 예를 들어 다음처럼 실행합니다.

```powershell
.\ai\run_api.ps1 -Port 8001
```

## POST /analyze 예시

```json
{
  "property_id": "P001",
  "address_query": "부산광역시 수영구 안심로 24",
  "planned_deposit": 200000000,
  "monthly_rent": 0,
  "guarantee_product_type": "jeonse_return",
  "user_note": "잔금일에 근저당을 말소한다고 들었습니다."
}
```

## 데모 매물

| property_id | 지역 | 주택유형 | 반환보증 |
|---|---|---|---|
| P001 | 부산광역시 수영구 | 다세대주택 | 확인 필요 |
| P002 | 부산광역시 강서구 | 오피스텔 | 가입 어려움 |
| P003 | 부산광역시 부산진구 | 아파트 | 공식 사전확인 완료 |
| P004 | 부산광역시 사하구 | 다가구주택 | 가입 신청 완료 |
| P005 | 부산광역시 해운대구 | 오피스텔 | 내부 추정 가능 |
| P006 | 부산광역시 동래구 | 연립주택 | 가입 완료 |

## 주의

현재 매물정보는 해커톤 데모용 샘플 데이터입니다. 실제 등기부 자동조회나 공식 보증심사 결과가 아니며, 응답의 `data_sources`와 `disclaimer`를 프론트 화면에 함께 표시해야 합니다.
# 운영 환경변수

```powershell
$env:CORS_ALLOW_ORIGINS="http://localhost:3000,https://dive-2026-teletubbies.hgumax.chatgpt.site"
$env:PROPERTY_DATA_PATH="C:\path\to\properties.json"
$env:PROPERTY_STORE_TTL_SECONDS="60"
$env:AI_API_BASE_URL="https://your-ai-api.example.com"
$env:AI_API_TIMEOUT_SECONDS="3"
$env:AI_API_ENABLED="true"
```

- `CORS_ALLOW_ORIGINS`: 쉼표로 구분한 브라우저 origin 목록입니다. 값이 없으면 `http://localhost:3000`, `https://dive-2026-teletubbies.hgumax.chatgpt.site`, 로컬 개발 주소가 기본 허용됩니다.
- `PROPERTY_DATA_PATH`: `sample_properties.csv` 대신 읽는 JSON 매물 데이터 저장소 경로입니다.
- `PROPERTY_STORE_TTL_SECONDS`: 매물 저장소 캐시 TTL입니다. TTL 전이라도 파일 수정 시간/크기가 바뀌면 다시 읽습니다.
- `AI_API_TIMEOUT_SECONDS`: AI API 호출 timeout입니다. 기본값은 `3.0`초입니다.
- `LOCAL_SIMILAR_CASES_ENABLED`: 운영 기본값은 `false`입니다. `true`로 켠 경우에만 AI 장애 시 명시적으로 `ai_api_status: "local_mock"` 상태와 함께 로컬 모의사례를 반환합니다.

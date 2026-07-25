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

## 현재 AI 연동 범위

현재 백엔드 MVP는 AI FastAPI 서버를 HTTP로 직접 호출하지 않습니다.

- `/analyze`는 `backend/similarity/search_cases.py`의 로컬 모의 유사사례를 사용합니다.
- 백엔드 요청 스키마에는 아직 `guarantee_product_type`이 없어 전세보증금반환보증과 임대보증금보증을 AI API에 구분 전달하지 않습니다.
- 백엔드 유사사례 응답과 `ai` 서비스의 유사사례 응답은 필드명과 유사도 단위가 다릅니다.
- 백엔드 위험점수는 미확인 정보를 점수에 포함하지만, 데이터분석 모듈은 미확인 정보를 확인사항으로 분리합니다.

## POST /analyze 예시

```json
{
  "property_id": "P001",
  "address_query": "부산광역시 수영구 안심로 24",
  "planned_deposit": 200000000,
  "monthly_rent": 0,
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

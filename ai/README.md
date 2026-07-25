# 안심계약 레이더 통합 분석 API

주소·계약 예정 보증금·상황 설명으로 시작해 매물정보, 반환보증 6단계, 확인된 위험과 미확인 정보, 유사 상담사례를 반환하는 FastAPI 서비스입니다. 전세보증금반환보증과 임대보증금보증은 요청 단계부터 분리합니다.

## 담당 범위

- 비식별 상담사례 938건 전처리 및 위험맥락 구조화
- 전세보증금반환보증과 임대보증금보증 분리
- 주택유형·권리·보증상태·보증금구간·상담문장 기반 유사사례 검색
- 고등학생도 이해할 수 있는 쉬운 설명과 확인 행동 생성
- 발제사 제공 7개 데이터의 상품별·주택유형별 통계 컨텍스트 제공
- 프론트 3개 화면용 매물정보·반환보증 상태 통합 응답
- 상세주소 축약, 필드별 출처·기준일, 합성데이터 품질 경고 제공

이 서비스의 위험단계는 확인된 규칙에 따른 계약 전 점검 단계입니다. 전세사기 여부, 사고확률, 법률 결론 또는 반환보증 공식 가입 가능 여부를 판단하지 않습니다.

## 제공 데이터 사용처

| 데이터 | 사용 방식 |
|---|---|
| 비식별 상담사례 938건 | 유사사례 검색과 쉬운 설명 |
| 임대보증 사고현황 | 임대보증금보증 상품별·주택유형별 참고 통계 |
| 전세·임대 채무자 경매현황 | 상품명이 없어 양쪽에 공통 참고 통계로 사용 |
| 전세·임대 채무자 배당내역 | `상품명` 기준 전세·임대 분리 집계 |
| 전세·임대 대위변제·회수현황 | `상품명` 기준 전세·임대 분리 집계 |
| 전세보증 사고현황 | 전세보증금반환보증 참고 통계 |
| 전세사고 주택유형·보증금비율 | 전세보증금반환보증 주택유형별 참고 통계 |

서로 다른 파일에는 공통 사례 ID가 없으므로 행 단위로 합치지 않습니다. 7개 원천은 모두 파이프라인에 등록하지만, 개별 요청에는 선택 상품과 공통 데이터만 적용하여 전세·임대 통계가 섞이지 않게 합니다. 상세주소는 API 컨텍스트에 저장하지 않고 시도 단위 집계만 사용합니다.

## 상품 유형

```text
jeonse_return  전세보증금반환보증
rental_deposit 임대보증금보증
unknown        보증상품 미확인
```

상담문장에 상품명이 명확한 경우만 상품 태그를 붙입니다. 상품을 확인할 수 없는 사례는 임의로 분류하지 않습니다.

## 설치

Python 3.10 이상과 PowerShell을 기준으로 합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 데이터 생성

`data/raw`의 7개 원본에서 검색데이터와 상품별 집계를 다시 생성합니다.

```powershell
.\run_data_pipeline.ps1
```

생성 파일:

```text
data/processed/consultations_clean.csv
data/processed/structured_cases.jsonl
data/processed/product_context.json
```

## API 실행

```powershell
.\run_api.ps1
```

- 상태 확인: `http://127.0.0.1:8000/health`
- Swagger 문서: `http://127.0.0.1:8000/docs`

## 프론트 3개 화면 연결

팀 공통 설명서와 같은 연결 순서는 다음과 같습니다.

```http
GET /properties/search?q=부산광역시
GET /properties/MOCK-001
POST /analyze
```

1. 첫 화면의 주소 검색창에서 `/properties/search`를 호출합니다.
2. 사용자가 선택한 `property_id`와 보증금을 `/analyze`에 보냅니다.
3. `/analyze` 응답을 저장해 매물정보·반환보증·분석·AI 사례 화면에서 나눠 씁니다.

```json
{
  "property_id": "MOCK-001",
  "deposit": 200000000,
  "user_text": "집주인이 잔금일에 근저당을 말소한다고 했습니다.",
  "top_k": 3
}
```

화면별 사용 필드:

| 화면 | 응답 필드 |
|---|---|
| 1. 주소·보증금 입력 | `/properties/search` 결과와 `/analyze` 요청값 |
| 2. 매물정보 확인 | `property`, `property_snapshot.cards` |
| 3. 반환보증 상태 | `guarantee` |
| 이후 위험분석 | `analysis`, `similar_cases`, `checklist` |
| 데이터 근거 | `historical_context`, `data_usage` |

모의 매물에 상품 유형이 저장돼 있어 `/analyze`가 전세·임대를 자동으로 분리합니다. 실제 자료를 직접 넘기는 하위 API에서는 `guarantee_product_type`을 반드시 `jeonse_return` 또는 `rental_deposit`으로 보냅니다.

반환보증 드롭다운과 4개 탭 값은 다음 API에서 가져옵니다.

```http
GET /api/contract-options
```

화면 그룹명은 팀 설명서와 동일합니다.

```text
check_required 확인 필요
in_progress    가입 절차 진행
protected      보호장치 확보
deep_analysis  심층분석 필요
```

조건 변경 화면은 다음 API를 사용합니다.

```http
POST /simulate
```

```json
{
  "property_id": "MOCK-001",
  "deposit": 200000000,
  "changes": {
    "mortgage_status": "none",
    "guarantee_status": "officially_eligible"
  }
}
```

응답의 `before`, `after`, `comparison`을 사용합니다. 시뮬레이션에서 말소를 선택해도 공식 확인으로 간주하지 않으므로 분석 신뢰도는 자동으로 올라가지 않습니다.

### 모의 화면과 실제 연동

- `data/mock_properties.json`: 서로 다른 흐름을 시연하는 모의 매물 5개
- `data/location_context.json`: 위험단계에 포함되지 않는 모의 입지 참고정보
- `/analyze`: 모의 매물 시연용 팀 공통 API
- `/api/contract-analysis`: 실제 주소조회 결과를 직접 전달할 때 사용하는 하위 통합 API
- 실제 확인자료가 없으면 값을 만들지 않고 `unknown`과 `확인 필요`를 반환합니다.
- 백엔드가 건축물대장·가격·권리·보증 자료를 조회한 경우 `property_facts`와 `guarantee_fact`에 필드별 출처와 기준일을 넣어 전달합니다.
- 제공 합성데이터는 주소별 등기나 주택가액 원천이 아니므로 특정 주소의 사실값으로 사용하지 않습니다.

실제 확인값 전달 예시:

```json
{
  "property_facts": {
    "housing_type": {
      "value": "아파트",
      "source": {
        "source_type": "official",
        "source_name": "건축물대장 연동",
        "reference_date": "2026-07-25"
      }
    },
    "reference_value": {
      "amount": 300000000,
      "value_type": "official_reference_value",
      "source": {
        "source_type": "official",
        "source_name": "공식 가격자료 연동",
        "reference_date": "2026-07-25"
      }
    }
  }
}
```

## 유사사례 요청

```http
POST /api/similar-cases
Content-Type: application/json
```

```json
{
  "property_data": {
    "property_id": "MOCK-PROPERTY-001",
    "region_sido": "부산광역시",
    "guarantee_product_type": "jeonse_return",
    "housing_type": "다세대주택",
    "deposit": 180000000,
    "senior_rights": "근저당",
    "guarantee_status": "unknown"
  },
  "analysis": {
    "confirmed_risks": [
      {
        "code": "MORTGAGE_EXISTS",
        "title": "선순위 근저당 확인",
        "severity": "high"
      }
    ],
    "required_checks": []
  },
  "user_text": "잔금일에 근저당을 말소한다고 했습니다.",
  "top_k": 3
}
```

응답의 주요 필드:

- `similar_cases`: 선택 상품과 같은 상담사례를 우선한 상위 결과
- `product_context`: 선택 상품에 해당하는 발제사 데이터 집계 출처
- `meta.selected_product_type`: 적용된 상품 유형
- `meta.product_separation_applied`: 상품별 분리 적용 여부
- `meta.is_accident_probability`: 항상 `false`

## 테스트

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 주의사항

- `similarity`는 상담사례가 비슷한 정도이며 위험도나 사고확률이 아닙니다.
- 상품명을 확인할 수 없는 상담사례는 `unknown`으로 유지합니다.
- 통계 컨텍스트는 발제사 제공 합성자료의 집계값이며 실제 시장 전체를 대표하지 않습니다.
- 현재 쉬운 설명은 안전검사를 포함한 템플릿 방식이며 생성형 AI 연동 시에도 같은 금지 규칙을 적용해야 합니다.

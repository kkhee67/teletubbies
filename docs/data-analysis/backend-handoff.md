# 데이터 분석 결과 전달 안내

이 문서는 데이터 분석 결과를 백엔드 담당자가 연결할 때 필요한 내용만 정리합니다. HTTP API 라우터와 프론트엔드는 수정하지 않았습니다.

## 전달 파일

| 파일 | 용도 |
|---|---|
| `backend/data/data_manifest.json` | 기준 데이터 파일, 실제·샘플 구분, 데이터 버전과 갱신시각 |
| `backend/data/analysis_api_contract.json` | 요청·응답 필드, 허용값, 오류 처리 계약 |
| `backend/data/mock_properties.json` | 시연용 모의 매물 5건 |
| `backend/data/location_context.json` | 위험단계에 반영하지 않는 입지 참고정보 |
| `backend/data/sample_analysis_results.json` | 입력과 전체 응답 예시 5건 |
| `backend/scoring/risk_rules.py` | 설명 가능한 위험 규칙과 결과 생성 함수 |
| `backend/scoring/confidence.py` | 필수정보 확인 정도 계산 |

## 백엔드에서 넘길 값

시연용 모의 매물 분석에는 아래 두 값만 필요합니다.

```json
{
  "property_id": "MOCK-005",
  "planned_deposit": 330000000
}
```

- `property_id`: `mock_properties.json`에 존재하는 ID
- `planned_deposit`: 원 단위의 0보다 큰 정수

## 연결 지점

백엔드 담당자는 HTTP 요청을 받은 뒤 아래 함수를 호출하면 됩니다.

```python
from backend.scoring.service import analyze_sample

result = analyze_sample(
    property_id=request_data["property_id"],
    planned_deposit=request_data["planned_deposit"],
)
```

`result`는 그대로 JSON 직렬화할 수 있는 딕셔너리입니다. API 경로, 요청 검증 방식, HTTP 응답 객체는 백엔드 담당자가 현재 서버 구조에 맞게 결정합니다.

실제 매물정보를 연결할 때는 `backend.scoring.risk_rules.analyze_property()`에 표준화된 매물정보와 보증금을 전달합니다. 표준 필드는 `docs/data-analysis/mapping.md`를 따릅니다.

실제 매물 직접 호출에서는 상태값을 `"exists"` 같은 평면 문자열로 넘기지 않습니다. 각 필드 안에 값과 출처정보를 함께 넣어야 합니다.

```json
{
  "dataset_type": "real",
  "data_version": "2026-07-26-v1",
  "updated_at": "2026-07-26T01:58:29+09:00",
  "mortgage_status": {
    "value": "exists",
    "source_type": "official",
    "source_name": "등기 확인자료",
    "reference_date": "2026-07-25",
    "retrieved_at": "2026-07-26T01:58:29+09:00"
  },
  "reference_value": {
    "amount": 350000000,
    "value_type": "official_price",
    "comparison_unit_confirmed": true,
    "source_type": "official",
    "source_name": "가격 확인자료",
    "reference_date": "2026-07-25",
    "retrieved_at": "2026-07-26T01:58:29+09:00"
  }
}
```

`property_type`, `mortgage_status`, `seizure_status`, `joint_collateral`, `guarantee_status`, `housing_required_info`는 같은 방식으로 출처정보를 필드 내부에 둡니다.

## 기준 데이터와 버전 확인

- `backend/data/data_manifest.json`은 설명 가능한 위험 분석 모듈에서 사용할 기준 파일만 지정합니다.
- 매물 검색 결과와 분석 결과에 `dataset_type`, `data_version`, `updated_at`을 함께 전달합니다.
- 검색 시점과 분석 시점의 `data_version`이 다르면 매물을 다시 조회한 뒤 분석합니다.
- 내부 샘플 서비스는 호출할 때마다 JSON 파일을 다시 읽으므로 데이터 변경에 서버 재시작이 필요하지 않습니다.
- 공개 HTTP API에서 버전을 비교하고 재조회하는 동작은 백엔드 담당자가 연결해야 합니다.
- `ai/data`와 기존 `sample_properties.csv`는 이 데이터 분석 모듈의 기준 파일로 선언하지 않습니다.

## 응답에서 사용할 부분

- `analysis.risk_stage`: 화면에 표시할 위험단계
- `analysis.confirmed_risks`: 자료로 확인된 위험과 근거·행동 안내
- `analysis.required_checks`: 정보가 없거나 검증되지 않아 추가로 확인할 항목
- `analysis.analysis_confidence`: 필수정보가 확인된 정도
- `property.dataset_type`: 실제 데이터인지 합성 시연 데이터인지 구분
- `property.data_version`: 검색·분석 시점 비교용 데이터 버전
- `property.updated_at`: 매물 레코드 갱신시각
- `guarantee`: 반환보증 상태와 화면용 문구
- `location_context`: 공항·군사시설·교통계획 등 입지 참고정보

`similar_cases`와 `checklist`는 다른 담당자가 채울 자리이므로 데이터 분석 파트에서는 빈 배열로 반환합니다.

`confirmed_risks`의 각 항목에는 `code`, `title`, `severity`, `explanation`, `action`이 들어갑니다. `required_checks`에는 `code`, `title`, `severity`, `action`이 들어가며 `explanation`은 반환하지 않습니다.

## 샘플 응답 보는 방법

`backend/data/sample_analysis_results.json`은 API 응답 하나가 아니라 아래 구조의 테스트 샘플 배열입니다.

```json
[
  {
    "input": {"property_id": "MOCK-005", "planned_deposit": 330000000},
    "result": {"property": {}, "guarantee": {}, "analysis": {}}
  }
]
```

- `result`가 실제 API에 전달할 분석 응답입니다.
- `input.purpose`는 샘플의 목적을 설명하기 위한 값이며 실제 요청에는 보내지 않습니다.
- 입지정보를 전달하지 않으면 `location_context`에는 `included_in_risk_score: false`만 있을 수 있습니다. `items`와 출처정보는 선택값입니다.

## 예외 처리 권장값

| 상황 | 모듈 예외 | 권장 HTTP 상태 |
|---|---|---|
| 존재하지 않는 `property_id` | `KeyError` | `404` |
| 보증금이 숫자가 아니거나 0 이하 | `ValueError` | `400` |

## 해석 시 주의사항

- `risk_stage`는 사고확률이나 법률적 판단이 아닙니다.
- `analysis_confidence`는 안전점수가 아니라 입력정보의 확인 정도입니다.
- `기본 확인`은 해당 계약이 안전하다는 의미가 아닙니다.
- 모르는 값은 안전으로 처리하지 않고 `required_checks`에 넣습니다.
- 입지정보는 위험단계를 낮추지 않으며 가격 상승을 보장하지 않습니다.
- `risk_score`와 `accident_probability` 필드는 제공하지 않습니다.
- `synthetic` 데이터의 `official`·`enrolled` 값은 기능 검증용 시나리오이며 실제 증빙이 아닙니다.

## 연결 전 확인

```powershell
python -m unittest discover -s tests -v
```

테스트 통과 후 `backend/data/sample_analysis_results.json`과 실제 함수 결과의 필드 구조가 같은지 확인하면 됩니다.

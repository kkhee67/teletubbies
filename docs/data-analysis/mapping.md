# 데이터 분석 표준 매핑

원본 데이터는 수정하지 않고 아래 표준 필드로 변환합니다. 값이 애매하면 추측하지 않고 `unknown`으로 둡니다.

| 표준 필드 | 의미 | 허용값 또는 형식 |
|---|---|---|
| `property_id` | 저장·연결용 매물 ID | 문자열 |
| `display_address` | 화면용 축약 주소 | 문자열 |
| `property_type.value` | 표준 주택유형 | `apartment`, `officetel`, `multi_household`, `multi_unit`, `row_house`, `detached`, `unknown` |
| `reference_value.amount` | 참고 주택가액 | 양의 정수 |
| `reference_value.value_type` | 가격 종류 | 공시가격·감정가·실거래가·모의 추정값 등 |
| `reference_value.comparison_unit_confirmed` | 보증금과 가격의 평가단위 일치 확인 | `true`, `false` |
| `mortgage_status.value` | 근저당 상태 | `none`, `exists`, `promised_removal`, `removed`, `unknown` |
| `seizure_status.value` | 압류·가압류 | `none`, `exists`, `unknown` |
| `joint_collateral.value` | 공동담보 | `none`, `exists`, `unknown` |
| `guarantee_status.value` | 반환보증 상태 | `estimated_eligible`, `officially_eligible`, `applied`, `enrolled`, `ineligible`, `unknown` |
| `housing_required_info.value` | 주택유형별 필수 확인정보 | 유형별 boolean 필드 |
| `down_contract_requested` | 실제 보증금과 다른 계약서 작성 요구 | `true`, `false` |
| `source_type` | 개별 필드 출처 종류 | `mock`, `official`, `user_confirmed` |
| `reference_date` | 정보 기준일 | `YYYY-MM-DD` |

## HUG·상담 데이터 사용 원칙

- HUG 사고자료는 주택유형별 보증금비율과 사고 이후 경매·배당 특성을 설명하는 참고 통계로 사용합니다.
- 정상계약 전체 분모가 없으므로 사고확률로 표현하지 않습니다.
- 비식별 상담자료의 미확인 값은 위험사실이 아니라 `required_checks` 생성 근거로 사용합니다.
- 주택가액의 출처가 확인되어도 개별 호실과 건물 전체 가액 등 평가단위가 다르면 보증금비율 위험신호를 생성하지 않습니다.
- 상세주소는 저장하지 않고 `property_id`와 축약 주소를 사용합니다.

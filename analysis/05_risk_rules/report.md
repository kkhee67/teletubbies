# 5단계 최종 위험규칙·가중치 명세

> 결론: 100점 위험점수를 사용하지 않고, `risk_stage` + `confirmed_risks` + `required_checks` + `analysis_confidence`로 표시합니다.

## 1. 위험단계

| 우선순위 | 조건 | 결과 |
|---:|---|---|
| 1 | `high_count >= 2` | 계약 전 재검토 |
| 2 | `high_count == 1 or medium_count >= 2` | 주의 |
| 3 | `confirmed_risk_count > 0 or required_check_count > 0` | 추가 확인 필요 |
| 4 | `otherwise` | 기본 확인 |

- `기본 확인`은 안전 판정이 아닙니다.
- 위험신호는 숫자로 합산하지 않고 `high`/`medium`의 개수로 단계를 정합니다.
- `required_checks`는 개수가 많아도 확인된 위험으로 바꾸지 않습니다.

## 2. 확인된 위험신호

| 코드 | 조건 | 심각도 |
|---|---|---|
| `MORTGAGE_EXISTS` | mortgage_status.value == 'exists' and signal source is verified or explicitly mock demo | high |
| `MORTGAGE_REMOVAL_PROMISED` | mortgage_status.value == 'promised_removal' and signal source is verified or explicitly mock demo | high |
| `SEIZURE_EXISTS` | seizure_status.value == 'exists' and signal source is verified or explicitly mock demo | high |
| `JOINT_COLLATERAL_EXISTS` | joint_collateral.value == 'exists' and signal source is verified or explicitly mock demo | medium |
| `GUARANTEE_INELIGIBLE` | guarantee_status.value == 'ineligible' and signal source is verified or explicitly mock demo | high |
| `DOWN_CONTRACT_REQUESTED` | down_contract_requested == true | high |
| `HIGH_DEPOSIT_RATIO` | verified_comparable_reference_value == true and 90 <= deposit_ratio < 100 | medium |
| `HIGH_DEPOSIT_RATIO` | verified_comparable_reference_value == true and deposit_ratio >= 100 | high |

### 보증금비율 적용 조건

- 90% 이상 100% 미만: `medium`
- 100% 이상: `high`
- 참고 주택가액의 금액·가격종류·출처·기준일이 확인되고, 보증금과 가격의 평가단위가 같을 때만 위험신호로 생성합니다.
- 출처나 단위가 불명하면 비율은 참고로만 표시하고 `REFERENCE_VALUE_UNVERIFIED`를 추가합니다.
- 90%·100%는 공식 HUG 가입기준이나 사고확률이 아닌 MVP 재검토 구간입니다.

## 3. 확인 필요 정보

| 코드 | 생성 조건 |
|---|---|
| `PROPERTY_TYPE_UNKNOWN` | property_type.value == 'unknown' or signal source is unverified |
| `REFERENCE_VALUE_UNKNOWN` | reference_value.amount is missing or <= 0 |
| `REFERENCE_VALUE_UNVERIFIED` | reference value exists but amount/value_type/source_name/reference_date or verified source is incomplete |
| `VALUE_UNIT_COMPARABILITY_UNKNOWN` | reference_value.amount exists and reference_value.comparison_unit_confirmed != true |
| `MORTGAGE_UNKNOWN` | mortgage_status.value == 'unknown' or signal source is unverified |
| `SEIZURE_UNKNOWN` | seizure_status.value == 'unknown' or signal source is unverified |
| `JOINT_COLLATERAL_UNKNOWN` | joint_collateral.value == 'unknown' or signal source is unverified |
| `GUARANTEE_UNKNOWN` | guarantee_status.value == 'unknown' or claimed official status has unverified source |
| `GUARANTEE_ESTIMATED_ONLY` | guarantee_status.value == 'estimated_eligible' |
| `GUARANTEE_ENROLLMENT_NOT_COMPLETED` | guarantee_status.value in {'officially_eligible', 'applied'} |
| `SENIOR_TENANT_DEPOSITS_UNKNOWN` | property_type.value == 'multi_household' and senior tenant deposits are unverified |
| `OFFICETEL_USE_UNKNOWN` | property_type.value == 'officetel' and residential use is unverified |
| `VALUE_BASIS_WEAK` | property_type.value in {'multi_unit', 'row_house', 'detached'} and comparable value basis is unverified |

## 4. 반환보증 6단계 처리

| 상태 | 화면 그룹 | 규칙 처리 |
|---|---|---|
| `estimated_eligible` | `confirmation_required` | GUARANTEE_ESTIMATED_ONLY required check |
| `officially_eligible` | `in_progress` | GUARANTEE_ENROLLMENT_NOT_COMPLETED required check |
| `applied` | `in_progress` | GUARANTEE_ENROLLMENT_NOT_COMPLETED required check |
| `enrolled` | `protected` | no guarantee risk/check; does not cancel other risks |
| `ineligible` | `deep_analysis` | GUARANTEE_INELIGIBLE high risk |
| `unknown` | `confirmation_required` | GUARANTEE_UNKNOWN required check |

## 5. 분석 신뢰도 가중치

| 필드 | 가중치 | 확인 인정 조건 |
|---|---:|---|
| `property_type` | 1 | official/user_confirmed and known |
| `reference_value` | 2 | official/user_confirmed; positive amount, value_type, source_name, reference_date complete |
| `mortgage_status` | 2 | official/user_confirmed and value is not unknown |
| `seizure_status` | 2 | official/user_confirmed and value is not unknown |
| `joint_collateral` | 1 | official/user_confirmed and value is not unknown |
| `guarantee_status` | 2 | official/user_confirmed and status is officially_eligible/applied/enrolled/ineligible |
| `housing_required_info` | 1 | official/user_confirmed and all type-specific required values are confirmed |
| **합계** | **11** | `round(확인 가중치 / 11 * 100)` |

- 분석 신뢰도는 안전도가 아닙니다.
- `source_type=mock`은 신뢰도 가중치에 산입하지 않습니다.
- 모의 매물에 가상의 `official`/`user_confirmed` 상태를 넣어 시연할 때는 화면에 반드시 '모의 매물'을 표시합니다.

## 6. 위험단계에 넣지 않는 항목

- 주택유형 자체
- 공항·군부대·철도계획·개발계획 등 입지 참고정보
- 상담문장의 키워드 빈도
- 경매 배당 0원 비율·배당 회수율·소요일 통계
- 미상·미확인 값
- 반환보증 가입완료를 다른 확인된 위험의 상쇄값으로 사용하는 것

## 7. 데이터 근거 스냅샷

- 합성 사고자료 69,435건의 보증금비율 중앙값: **94.6%**
- 같은 자료의 90% 이상 비중: **59.1%**
- 합성 경매자료 32,542건의 배당 0원 비중: **64.9%**
- 비식별 상담 938건 중 선순위권리 미상: **63.7%**
- 위 수치는 규칙의 필요성을 설명하는 근거이며, 개별 계약의 사고확률이 아닙니다.

## 8. 6단계 구현 전 필수 수정점

- 임시 코드의 보증금비율 규칙은 참고가액 검증 전에 위험을 생성할 수 있으므로, 검증된 가액일 때만 `HIGH_DEPOSIT_RATIO`를 생성하도록 바꿔야 합니다.
- 100% 이상도 별도 코드로 나누지 않고 `HIGH_DEPOSIT_RATIO` 한 코드의 `high` 구간으로 통일합니다.
- 이 단계에서는 명세만 확정했으며 백엔드 규칙 코드는 6단계에서 수정합니다.

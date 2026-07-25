"""5단계: 1~4단계 결과를 바탕으로 MVP 위험규칙 명세를 확정한다.

이 스크립트는 사고확률이나 100점 위험점수를 학습하지 않는다. 제공된
합성 사고자료와 상담자료는 규칙의 방향과 설명 근거로만 사용한다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


RISK_STAGES = ["기본 확인", "추가 확인 필요", "주의", "계약 전 재검토"]
ALLOWED_RISK_SEVERITIES = {"high", "medium"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def determine_stage(high_count: int, medium_count: int, required_count: int) -> str:
    if high_count >= 2:
        return "계약 전 재검토"
    if high_count == 1 or medium_count >= 2:
        return "주의"
    if high_count or medium_count or required_count:
        return "추가 확인 필요"
    return "기본 확인"


def build_spec(step2: dict, step3: dict, step4: dict) -> dict[str, Any]:
    overall = step2["overall_stats"]
    consultation_unknown = step4["unknown_summary"]

    confirmed_risks = [
        {
            "code": "MORTGAGE_EXISTS",
            "condition": "mortgage_status.value == 'exists' and signal source is verified or explicitly mock demo",
            "severity": "high",
            "title": "선순위 근저당 확인",
            "action": "등기부 을구의 채권최고액과 순위를 확인한다.",
            "basis": "상담자료에서 근저당 설정 138건 중 중대 분쟁 포함 112건이었으나, 상담 표본 내부 비율이므로 사고확률을 의미하지 않는다.",
        },
        {
            "code": "MORTGAGE_REMOVAL_PROMISED",
            "condition": "mortgage_status.value == 'promised_removal' and signal source is verified or explicitly mock demo",
            "severity": "high",
            "title": "근저당 말소 미완료",
            "action": "잔금 지급 직전 최신 등기부에서 말소 완료를 재확인한다.",
            "basis": "말소 약속은 권리가 실제 삭제된 상태와 다르다.",
        },
        {
            "code": "SEIZURE_EXISTS",
            "condition": "seizure_status.value == 'exists' and signal source is verified or explicitly mock demo",
            "severity": "high",
            "title": "압류·가압류 확인",
            "action": "최신 등기부와 권리순위를 전문가와 확인한다.",
            "basis": "상담자료에서 압류·가압류 111건 중 중대 분쟁 포함 73건이었다. 일반 계약의 사고확률로는 해석하지 않는다.",
        },
        {
            "code": "JOINT_COLLATERAL_EXISTS",
            "condition": "joint_collateral.value == 'exists' and signal source is verified or explicitly mock demo",
            "severity": "medium",
            "title": "공동담보 확인",
            "action": "공동담보 목록과 전체 채권최고액을 확인한다.",
            "basis": "개별 매물만으로 배당 순서와 회수가능액을 판단하기 어렵다.",
        },
        {
            "code": "GUARANTEE_INELIGIBLE",
            "condition": "guarantee_status.value == 'ineligible' and signal source is verified or explicitly mock demo",
            "severity": "high",
            "title": "반환보증 가입 어려움",
            "action": "공식 불가 사유를 확인하고 계약조건을 재검토한다.",
            "basis": "반환보증을 보호장치로 사용하기 어려운 확인 상태이다. 가입 완료도 다른 권리위험을 상쇄하지 않는다.",
        },
        {
            "code": "DOWN_CONTRACT_REQUESTED",
            "condition": "down_contract_requested == true",
            "severity": "high",
            "title": "다운계약 요구",
            "action": "실제 보증금과 다른 계약서 작성을 거절하고 전문가에게 상담한다.",
            "basis": "실제 계약조건과 서류 내용의 불일치는 독립적으로 확인된 위험신호다.",
        },
        {
            "code": "HIGH_DEPOSIT_RATIO",
            "condition": "verified_comparable_reference_value == true and 90 <= deposit_ratio < 100",
            "severity": "medium",
            "title": "보증금비율 90% 이상",
            "action": "가격 산정 근거와 보증금 조정 가능성을 확인한다.",
            "basis": f"합성 사고자료 {overall['count']:,}건의 {overall['over_90_rate']:.1%}가 90% 이상이었다. 정상계약 분모가 없으므로 90%는 MVP 확인 구간이지 사고확률 기준이 아니다.",
        },
        {
            "code": "HIGH_DEPOSIT_RATIO",
            "condition": "verified_comparable_reference_value == true and deposit_ratio >= 100",
            "severity": "high",
            "title": "보증금이 참고 주택가액 이상",
            "action": "가격 산정 근거를 재확인하고 보증금 조정을 검토한다.",
            "basis": "보증금만으로 참고 주택가액을 넘거나 같아 가격 완충여력이 없는 구간이다. 가격단위와 보증금단위가 같을 때만 적용한다.",
        },
    ]

    required_checks = [
        {"code": "PROPERTY_TYPE_UNKNOWN", "condition": "property_type.value == 'unknown' or signal source is unverified", "action": "건축물대장에서 주택유형을 확인한다."},
        {"code": "REFERENCE_VALUE_UNKNOWN", "condition": "reference_value.amount is missing or <= 0", "action": "가격자료의 종류·출처·기준일을 확인한다."},
        {"code": "REFERENCE_VALUE_UNVERIFIED", "condition": "reference value exists but amount/value_type/source_name/reference_date or verified source is incomplete", "action": "비율은 참고로만 보이고 확인된 위험으로 사용하지 않는다."},
        {"code": "VALUE_UNIT_COMPARABILITY_UNKNOWN", "condition": "reference_value.amount exists and reference_value.comparison_unit_confirmed != true", "action": "개별 보증금과 건물 전체가액을 단순 비교하지 말고 평가단위를 맞춘다."},
        {"code": "MORTGAGE_UNKNOWN", "condition": "mortgage_status.value == 'unknown' or signal source is unverified", "action": "최신 등기부 을구를 확인한다."},
        {"code": "SEIZURE_UNKNOWN", "condition": "seizure_status.value == 'unknown' or signal source is unverified", "action": "최신 등기부에서 압류·가압류를 확인한다."},
        {"code": "JOINT_COLLATERAL_UNKNOWN", "condition": "joint_collateral.value == 'unknown' or signal source is unverified", "action": "등기부의 공동담보목록을 확인한다."},
        {"code": "GUARANTEE_UNKNOWN", "condition": "guarantee_status.value == 'unknown' or claimed official status has unverified source", "action": "반환보증 공식 사전확인을 진행한다."},
        {"code": "GUARANTEE_ESTIMATED_ONLY", "condition": "guarantee_status.value == 'estimated_eligible'", "action": "내부 추정을 가입가능 확정으로 표현하지 않고 공식 사전확인을 받는다."},
        {"code": "GUARANTEE_ENROLLMENT_NOT_COMPLETED", "condition": "guarantee_status.value in {'officially_eligible', 'applied'}", "action": "보증서 발급 또는 가입완료 증빙을 확인한다."},
        {"code": "SENIOR_TENANT_DEPOSITS_UNKNOWN", "condition": "property_type.value == 'multi_household' and senior tenant deposits are unverified", "action": "선순위 임차보증금·다른 임차인 순위·건물 전체 권리를 확인한다."},
        {"code": "OFFICETEL_USE_UNKNOWN", "condition": "property_type.value == 'officetel' and residential use is unverified", "action": "건축물대장과 실제 용도, 보증 가입요건을 확인한다."},
        {"code": "VALUE_BASIS_WEAK", "condition": "property_type.value in {'multi_unit', 'row_house', 'detached'} and comparable value basis is unverified", "action": "실거래가·공시가격·감정가의 종류와 기준일을 확인한다."},
    ]

    confidence_weights = [
        {"field": "property_type", "weight": 1, "verified_when": "official/user_confirmed and known"},
        {"field": "reference_value", "weight": 2, "verified_when": "official/user_confirmed; positive amount, value_type, source_name, reference_date complete"},
        {"field": "mortgage_status", "weight": 2, "verified_when": "official/user_confirmed and value is not unknown"},
        {"field": "seizure_status", "weight": 2, "verified_when": "official/user_confirmed and value is not unknown"},
        {"field": "joint_collateral", "weight": 1, "verified_when": "official/user_confirmed and value is not unknown"},
        {"field": "guarantee_status", "weight": 2, "verified_when": "official/user_confirmed and status is officially_eligible/applied/enrolled/ineligible"},
        {"field": "housing_required_info", "weight": 1, "verified_when": "official/user_confirmed and all type-specific required values are confirmed"},
    ]

    scenarios = [
        {"name": "확인된 기본 사례", "high": 0, "medium": 0, "checks": 0, "expected_stage": "기본 확인"},
        {"name": "미확인 정보만 존재", "high": 0, "medium": 0, "checks": 4, "expected_stage": "추가 확인 필요"},
        {"name": "90% 이상 보증금비율 1개", "high": 0, "medium": 1, "checks": 0, "expected_stage": "추가 확인 필요"},
        {"name": "중간 위험 2개", "high": 0, "medium": 2, "checks": 0, "expected_stage": "주의"},
        {"name": "높은 위험 1개", "high": 1, "medium": 0, "checks": 2, "expected_stage": "주의"},
        {"name": "높은 위험 2개", "high": 2, "medium": 0, "checks": 1, "expected_stage": "계약 전 재검토"},
    ]

    return {
        "version": "1.0.0",
        "model_type": "explainable_rule_based_decision_support",
        "outputs_probability": False,
        "outputs_numeric_risk_score": False,
        "primary_outputs": ["risk_stage", "confirmed_risks", "required_checks", "analysis_confidence"],
        "signal_source_policy": {
            "verified_source_types": ["official", "user_confirmed"],
            "mock_demo_exception": "source_type=mock may exercise rules only when property.is_mock=true; the UI must label the result as mock",
            "unverified_absence_handling": "none/removed from an unverified source is a required check, not confirmed absence",
        },
        "risk_stages": RISK_STAGES,
        "stage_rules": [
            {"priority": 1, "condition": "high_count >= 2", "stage": "계약 전 재검토"},
            {"priority": 2, "condition": "high_count == 1 or medium_count >= 2", "stage": "주의"},
            {"priority": 3, "condition": "confirmed_risk_count > 0 or required_check_count > 0", "stage": "추가 확인 필요"},
            {"priority": 4, "condition": "otherwise", "stage": "기본 확인"},
        ],
        "confirmed_risk_rules": confirmed_risks,
        "required_check_rules": required_checks,
        "deposit_ratio_policy": {
            "formula": "planned_deposit / reference_value.amount * 100",
            "minimum_data_condition": "positive deposit and verified comparable reference value",
            "bands": [
                {"min_inclusive": 100, "severity": "high", "code": "HIGH_DEPOSIT_RATIO"},
                {"min_inclusive": 90, "max_exclusive": 100, "severity": "medium", "code": "HIGH_DEPOSIT_RATIO"},
                {"max_exclusive": 90, "severity": None, "code": None},
            ],
            "unverified_reference_handling": "display provisional ratio only; add REFERENCE_VALUE_UNVERIFIED and do not create HIGH_DEPOSIT_RATIO",
            "multi_household_handling": "do not treat a low individual-deposit/building-value ratio as safe; require senior tenant deposits and comparable units",
            "threshold_notice": "90% and 100% are transparent MVP review bands, not official HUG eligibility rules or estimated accident probabilities.",
        },
        "guarantee_status_policy": {
            "estimated_eligible": {"group": "confirmation_required", "effect": "GUARANTEE_ESTIMATED_ONLY required check"},
            "officially_eligible": {"group": "in_progress", "effect": "GUARANTEE_ENROLLMENT_NOT_COMPLETED required check"},
            "applied": {"group": "in_progress", "effect": "GUARANTEE_ENROLLMENT_NOT_COMPLETED required check"},
            "enrolled": {"group": "protected", "effect": "no guarantee risk/check; does not cancel other risks"},
            "ineligible": {"group": "deep_analysis", "effect": "GUARANTEE_INELIGIBLE high risk"},
            "unknown": {"group": "confirmation_required", "effect": "GUARANTEE_UNKNOWN required check"},
        },
        "confidence_policy": {
            "meaning": "percentage of required analysis information verified; not safety or probability",
            "formula": "round(sum(verified field weights) / 11 * 100)",
            "verified_source_types": ["official", "user_confirmed"],
            "mock_source_weight": 0,
            "weights": confidence_weights,
            "total_weight": sum(row["weight"] for row in confidence_weights),
        },
        "excluded_from_risk_stage": [
            "주택유형 자체",
            "공항·군부대·철도계획·개발계획 등 입지 참고정보",
            "상담문장의 키워드 빈도",
            "경매 배당 0원 비율·배당 회수율·소요일 통계",
            "미상·미확인 값",
            "반환보증 가입완료를 다른 확인된 위험의 상쇄값으로 사용하는 것",
        ],
        "location_context_policy": {
            "included_in_risk_score": False,
            "required_metadata": ["source_name", "reference_date", "source_type"],
            "wording_rule": "describe constraints or official plans as reference information; do not assert price rise/fall",
        },
        "evidence_snapshot": {
            "synthetic_accident_deposit_ratio_rows": overall["count"],
            "synthetic_accident_deposit_ratio_median": overall["median_ratio"],
            "synthetic_accident_deposit_ratio_over_90_rate": overall["over_90_rate"],
            "synthetic_auction_rows": step3["auction"]["rows"],
            "synthetic_auction_zero_dividend_rate": step3["auction"]["zero_dividend_rate"],
            "synthetic_distribution_median_days": step3["distribution"]["median_distribution_days_nonnegative"],
            "consultation_rows": step4["rows"],
            "consultation_serious_dispute_count": step4["serious_dispute_count"],
            "consultation_unknown_housing_type_rate": consultation_unknown["housing_type"]["share"],
            "consultation_unknown_senior_rights_rate": consultation_unknown["senior_rights"]["share"],
            "consultation_unknown_guarantee_rate": consultation_unknown["guarantee"]["share"],
        },
        "validation_scenarios": scenarios,
        "implementation_notes_for_step_6": [
            "HIGH_DEPOSIT_RATIO must be generated only when the reference value is verified and comparable.",
            "Use one canonical HIGH_DEPOSIT_RATIO code with severity selected by the 90/100 bands.",
            "Keep unknown values out of confirmed_risks and add explicit required_checks instead.",
            "Mock fields may exercise demo rules, but source_type=mock contributes zero to analysis_confidence.",
            "Do not modify risk stage using location_context or post-accident recovery statistics.",
        ],
        "notices": [
            "기본 확인은 안전 판정이 아니라 현재 확인된 자료에서 강한 위험신호가 발견되지 않았다는 뜻이다.",
            "분석 신뢰도는 안전도가 아니라 필수정보의 확인 정도다.",
            "제공된 합성 사고자료와 상담자료는 전체 정상계약 분모가 없어 사고확률 추정에 사용하지 않는다.",
        ],
    }


def validate_spec(spec: dict[str, Any]) -> None:
    assert spec["outputs_probability"] is False
    assert spec["outputs_numeric_risk_score"] is False
    assert spec["risk_stages"] == RISK_STAGES
    assert spec["confidence_policy"]["total_weight"] == 11
    assert spec["confidence_policy"]["mock_source_weight"] == 0
    assert spec["location_context_policy"]["included_in_risk_score"] is False

    required_codes = [row["code"] for row in spec["required_check_rules"]]
    assert len(required_codes) == len(set(required_codes))
    assert all(row["severity"] in ALLOWED_RISK_SEVERITIES for row in spec["confirmed_risk_rules"])
    assert all("unknown" not in row["condition"].lower() for row in spec["confirmed_risk_rules"])

    for scenario in spec["validation_scenarios"]:
        actual = determine_stage(scenario["high"], scenario["medium"], scenario["checks"])
        assert actual == scenario["expected_stage"], (scenario["name"], actual)


def build_report(spec: dict[str, Any]) -> str:
    evidence = spec["evidence_snapshot"]
    lines = [
        "# 5단계 최종 위험규칙·가중치 명세",
        "",
        "> 결론: 100점 위험점수를 사용하지 않고, `risk_stage` + `confirmed_risks` + `required_checks` + `analysis_confidence`로 표시합니다.",
        "",
        "## 1. 위험단계",
        "",
        "| 우선순위 | 조건 | 결과 |",
        "|---:|---|---|",
    ]
    for row in spec["stage_rules"]:
        lines.append(f"| {row['priority']} | `{row['condition']}` | {row['stage']} |")

    lines.extend([
        "",
        "- `기본 확인`은 안전 판정이 아닙니다.",
        "- 위험신호는 숫자로 합산하지 않고 `high`/`medium`의 개수로 단계를 정합니다.",
        "- `required_checks`는 개수가 많아도 확인된 위험으로 바꾸지 않습니다.",
        "",
        "## 2. 확인된 위험신호",
        "",
        "| 코드 | 조건 | 심각도 |",
        "|---|---|---|",
    ])
    for row in spec["confirmed_risk_rules"]:
        lines.append(f"| `{row['code']}` | {row['condition']} | {row['severity']} |")

    lines.extend([
        "",
        "### 보증금비율 적용 조건",
        "",
        "- 90% 이상 100% 미만: `medium`",
        "- 100% 이상: `high`",
        "- 참고 주택가액의 금액·가격종류·출처·기준일이 확인되고, 보증금과 가격의 평가단위가 같을 때만 위험신호로 생성합니다.",
        "- 출처나 단위가 불명하면 비율은 참고로만 표시하고 `REFERENCE_VALUE_UNVERIFIED`를 추가합니다.",
        "- 90%·100%는 공식 HUG 가입기준이나 사고확률이 아닌 MVP 재검토 구간입니다.",
        "",
        "## 3. 확인 필요 정보",
        "",
        "| 코드 | 생성 조건 |",
        "|---|---|",
    ])
    for row in spec["required_check_rules"]:
        lines.append(f"| `{row['code']}` | {row['condition']} |")

    lines.extend([
        "",
        "## 4. 반환보증 6단계 처리",
        "",
        "| 상태 | 화면 그룹 | 규칙 처리 |",
        "|---|---|---|",
    ])
    for status, row in spec["guarantee_status_policy"].items():
        lines.append(f"| `{status}` | `{row['group']}` | {row['effect']} |")

    lines.extend([
        "",
        "## 5. 분석 신뢰도 가중치",
        "",
        "| 필드 | 가중치 | 확인 인정 조건 |",
        "|---|---:|---|",
    ])
    for row in spec["confidence_policy"]["weights"]:
        lines.append(f"| `{row['field']}` | {row['weight']} | {row['verified_when']} |")
    lines.extend([
        f"| **합계** | **{spec['confidence_policy']['total_weight']}** | `round(확인 가중치 / 11 * 100)` |",
        "",
        "- 분석 신뢰도는 안전도가 아닙니다.",
        "- `source_type=mock`은 신뢰도 가중치에 산입하지 않습니다.",
        "- 모의 매물에 가상의 `official`/`user_confirmed` 상태를 넣어 시연할 때는 화면에 반드시 '모의 매물'을 표시합니다.",
        "",
        "## 6. 위험단계에 넣지 않는 항목",
        "",
    ])
    for item in spec["excluded_from_risk_stage"]:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## 7. 데이터 근거 스냅샷",
        "",
        f"- 합성 사고자료 {evidence['synthetic_accident_deposit_ratio_rows']:,}건의 보증금비율 중앙값: **{evidence['synthetic_accident_deposit_ratio_median']:.1f}%**",
        f"- 같은 자료의 90% 이상 비중: **{evidence['synthetic_accident_deposit_ratio_over_90_rate']:.1%}**",
        f"- 합성 경매자료 {evidence['synthetic_auction_rows']:,}건의 배당 0원 비중: **{evidence['synthetic_auction_zero_dividend_rate']:.1%}**",
        f"- 비식별 상담 {evidence['consultation_rows']:,}건 중 선순위권리 미상: **{evidence['consultation_unknown_senior_rights_rate']:.1%}**",
        "- 위 수치는 규칙의 필요성을 설명하는 근거이며, 개별 계약의 사고확률이 아닙니다.",
        "",
        "## 8. 6단계 구현 전 필수 수정점",
        "",
        "- 임시 코드의 보증금비율 규칙은 참고가액 검증 전에 위험을 생성할 수 있으므로, 검증된 가액일 때만 `HIGH_DEPOSIT_RATIO`를 생성하도록 바꿔야 합니다.",
        "- 100% 이상도 별도 코드로 나누지 않고 `HIGH_DEPOSIT_RATIO` 한 코드의 `high` 구간으로 통일합니다.",
        "- 이 단계에서는 명세만 확정했으며 백엔드 규칙 코드는 6단계에서 수정합니다.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-dir", type=Path, default=Path("analysis"))
    parser.add_argument("--output-dir", type=Path, default=Path("analysis/05_risk_rules"))
    args = parser.parse_args()

    step2 = load_json(args.analysis_dir / "02_housing_deposit_ratio" / "housing_deposit_ratio.json")
    step3 = load_json(args.analysis_dir / "03_auction_recovery" / "auction_recovery.json")
    step4 = load_json(args.analysis_dir / "04_consultation_context" / "consultation_context.json")
    spec = build_spec(step2, step3, step4)
    validate_spec(spec)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "risk_rules_spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "report.md").write_text(build_report(spec), encoding="utf-8")

    print("risk rule specification: PASS")
    print(f"confirmed rule bands: {len(spec['confirmed_risk_rules'])}")
    print(f"required check rules: {len(spec['required_check_rules'])}")
    print(f"confidence total weight: {spec['confidence_policy']['total_weight']}")
    print(f"saved: {args.output_dir}")


if __name__ == "__main__":
    main()

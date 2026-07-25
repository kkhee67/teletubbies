"""4단계: 비식별 임대차상담 938건의 위험맥락을 분석한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

SERIOUS_DISPUTES = {"경매·공매", "보증금미반환", "전세사기"}
TEXT_COLUMNS = ["상황요약", "담당자의견", "특이사항"]
KEYWORDS = [
    "근저당",
    "말소",
    "공동담보",
    "선순위",
    "보증보험",
    "미반환",
    "경매",
    "공매",
    "압류",
    "가압류",
    "전세사기",
    "다운계약",
    "임차권등기",
    "다가구",
    "오피스텔",
]

HOUSING_MAP = {
    "아파트": "아파트",
    "오피스텔": "오피스텔",
    "다가구주택": "다가구주택",
    "다세대주택": "다세대·빌라",
    "빌라": "다세대·빌라",
    "원룸·도시형": "원룸·도시형",
    "공공임대": "공공임대",
    "미상": "미상",
}


def distribution(frame: pd.DataFrame, column: str) -> list[dict]:
    counts = frame[column].fillna("<결측>").value_counts(dropna=False)
    return [
        {"value": str(value), "count": int(count), "share": round(float(count / len(frame)), 4)}
        for value, count in counts.items()
    ]


def grouped_serious(frame: pd.DataFrame, column: str) -> list[dict]:
    temp = frame.assign(is_serious=frame["분쟁유형"].isin(SERIOUS_DISPUTES))
    rows = []
    for value, group in temp.groupby(column, dropna=False):
        display = "<결측>" if pd.isna(value) else str(value)
        rows.append({
            "value": display,
            "count": int(len(group)),
            "serious_dispute_count": int(group["is_serious"].sum()),
            "serious_dispute_share_in_consultations": round(float(group["is_serious"].mean()), 4),
            "top_disputes": {
                str(k): int(v) for k, v in group["분쟁유형"].value_counts().head(3).items()
            },
        })
    rows.sort(key=lambda row: row["count"], reverse=True)
    return rows


def keyword_patterns(frame: pd.DataFrame) -> list[dict]:
    text = frame[TEXT_COLUMNS].fillna("").astype(str).agg(" ".join, axis=1)
    rows = []
    for keyword in KEYWORDS:
        mask = text.str.contains(keyword, regex=False)
        serious = frame.loc[mask, "분쟁유형"].isin(SERIOUS_DISPUTES)
        rows.append({
            "keyword": keyword,
            "record_count": int(mask.sum()),
            "record_share": round(float(mask.mean()), 4),
            "serious_dispute_count": int(serious.sum()),
            "serious_dispute_share_in_keyword_records": (
                round(float(serious.mean()), 4) if mask.sum() else None
            ),
        })
    rows.sort(key=lambda row: row["record_count"], reverse=True)
    return rows


def top_combinations(frame: pd.DataFrame) -> list[dict]:
    columns = ["주택유형_표준", "선순위권리", "보증보험", "분쟁유형"]
    counts = frame.groupby(columns, dropna=False).size().sort_values(ascending=False).head(20)
    return [
        {
            "housing_type": str(index[0]),
            "senior_rights": str(index[1]),
            "guarantee": str(index[2]),
            "dispute_type": str(index[3]),
            "count": int(count),
        }
        for index, count in counts.items()
    ]


def build_report(result: dict) -> str:
    unknown = result["unknown_summary"]
    lines = [
        "# 4단계 상담데이터 위험맥락 분석",
        "",
        "> 비식별 법률상담 938건의 내부 분포입니다. 전체 임대차계약의 사고확률을 의미하지 않습니다.",
        "",
        f"- 전체 상담: {result['rows']:,}건",
        f"- 중대 분쟁(경매·공매, 보증금미반환, 전세사기): {result['serious_dispute_count']:,}건({result['serious_dispute_share']:.1%})",
        "",
        "## 미확인 정보",
        "",
        f"- 주택유형 미상: **{unknown['housing_type']['count']:,}건({unknown['housing_type']['share']:.1%})**",
        f"- 선순위권리 미상: **{unknown['senior_rights']['count']:,}건({unknown['senior_rights']['share']:.1%})**",
        f"- 보증보험 미상: **{unknown['guarantee']['count']:,}건({unknown['guarantee']['share']:.1%})**",
        "- 따라서 `미상`을 확인된 위험으로 처리하지 않고 `required_checks`로 분리해야 합니다.",
        "",
        "## 주요 분쟁유형",
        "",
        "| 분쟁유형 | 건수 | 비중 |",
        "|---|---:|---:|",
    ]
    for row in result["distributions"]["dispute_type"]:
        lines.append(f"| {row['value']} | {row['count']:,} | {row['share']:.1%} |")
    lines.extend([
        "",
        "## 주택유형별 상담맥락",
        "",
        "| 주택유형 | 상담 건수 | 중대 분쟁 포함 건수 | 해당 상담군 내 비율 |",
        "|---|---:|---:|---:|",
    ])
    for row in result["housing_patterns"]:
        lines.append(
            f"| {row['value']} | {row['count']:,} | {row['serious_dispute_count']:,} | "
            f"{row['serious_dispute_share_in_consultations']:.1%} |"
        )
    lines.extend([
        "",
        "## 선순위권리 상태별 상담맥락",
        "",
        "| 선순위권리 | 상담 건수 | 중대 분쟁 포함 건수 | 해당 상담군 내 비율 |",
        "|---|---:|---:|---:|",
    ])
    for row in result["rights_patterns"]:
        lines.append(
            f"| {row['value']} | {row['count']:,} | {row['serious_dispute_count']:,} | "
            f"{row['serious_dispute_share_in_consultations']:.1%} |"
        )
    lines.extend([
        "",
        "## 보증보험 상태별 상담맥락",
        "",
        "| 보증보험 | 상담 건수 | 중대 분쟁 포함 건수 | 해당 상담군 내 비율 |",
        "|---|---:|---:|---:|",
    ])
    for row in result["guarantee_patterns"]:
        lines.append(
            f"| {row['value']} | {row['count']:,} | {row['serious_dispute_count']:,} | "
            f"{row['serious_dispute_share_in_consultations']:.1%} |"
        )
    lines.extend([
        "",
        "## 상담문장 반복 키워드",
        "",
        "| 키워드 | 포함 상담 | 전체 상담 내 비중 |",
        "|---|---:|---:|",
    ])
    for row in result["keyword_patterns"]:
        if row["record_count"]:
            lines.append(
                f"| {row['keyword']} | {row['record_count']:,} | {row['record_share']:.1%} |"
            )
    lines.extend([
        "",
        "## 위험규칙에 사용할 수 있는 부분",
        "",
        "- 근저당·압류·가압류·선순위권리 존재는 확인된 경우 `confirmed_risks` 후보입니다.",
        "- 선순위권리·보증보험·주택유형 미상은 `required_checks`로 분리합니다.",
        "- 말소 약속은 말소 완료와 구분하고, 잔금 전 등기부 재확인 행동으로 연결합니다.",
        "- 상담문장 키워드는 위험점수를 직접 올리는 값이 아니라 유사사례 검색과 쉬운 설명의 보조 특징으로 사용합니다.",
        "- 상담을 요청한 사례만 모인 자료이므로 상태별 비중을 일반 계약의 사고확률로 표현하지 않습니다.",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("analysis/04_consultation_context"))
    args = parser.parse_args()

    source = next(args.data_dir.glob("*상담데이터*.xlsx"))
    frame = pd.read_excel(source, sheet_name="비식별_상담데이터")
    frame["주택유형_표준"] = frame["주택유형"].map(HOUSING_MAP).fillna(frame["주택유형"])
    serious_mask = frame["분쟁유형"].isin(SERIOUS_DISPUTES)

    def unknown(column):
        mask = frame[column].isna() | frame[column].eq("미상")
        return {"count": int(mask.sum()), "share": round(float(mask.mean()), 4)}

    result = {
        "source_file": source.name,
        "sheet": "비식별_상담데이터",
        "rows": int(len(frame)),
        "duplicate_rows": int(frame.duplicated().sum()),
        "serious_dispute_definition": sorted(SERIOUS_DISPUTES),
        "serious_dispute_count": int(serious_mask.sum()),
        "serious_dispute_share": round(float(serious_mask.mean()), 4),
        "unknown_summary": {
            "housing_type": unknown("주택유형"),
            "senior_rights": unknown("선순위권리"),
            "guarantee": unknown("보증보험"),
        },
        "distributions": {
            "housing_type": distribution(frame, "주택유형_표준"),
            "senior_rights": distribution(frame, "선순위권리"),
            "guarantee": distribution(frame, "보증보험"),
            "dispute_type": distribution(frame, "분쟁유형"),
            "stage": distribution(frame, "진행단계"),
        },
        "housing_patterns": grouped_serious(frame, "주택유형_표준"),
        "rights_patterns": grouped_serious(frame, "선순위권리"),
        "guarantee_patterns": grouped_serious(frame, "보증보험"),
        "keyword_patterns": keyword_patterns(frame),
        "top_combinations": top_combinations(frame),
        "interpretation_notice": (
            "법률상담을 요청한 비식별 사례의 내부 분포이며 전체 임대차계약의 사고확률이 아닙니다."
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "consultation_context.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "report.md").write_text(build_report(result), encoding="utf-8")
    print(f"rows: {len(frame):,}")
    print(f"serious disputes: {result['serious_dispute_count']:,}")
    print(f"saved: {args.output_dir}")


if __name__ == "__main__":
    main()

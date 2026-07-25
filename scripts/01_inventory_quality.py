"""1단계: 제공 데이터 8개의 구조와 품질을 점검한다.

원본은 수정하지 않고 JSON과 Markdown 보고서만 생성한다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


SENSITIVE_SAMPLE_COLUMNS = {
    "상황요약",
    "담당자의견",
    "특이사항",
}
SENSITIVE_SAMPLE_TOKENS = ("주소", "소재지", "상세", "시도명", "시도구")


def read_csv_safe(path: Path) -> tuple[pd.DataFrame, str]:
    for encoding in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"인코딩을 확인할 수 없습니다: {path.name}")


def json_value(value: Any):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def profile_frame(df: pd.DataFrame) -> dict:
    missing = df.isna().sum()
    columns = []
    for column in df.columns:
        series = df[column]
        column_name = str(column)
        redact_samples = (
            column_name in SENSITIVE_SAMPLE_COLUMNS
            or column_name.startswith("Unnamed")
            or any(token in column_name for token in SENSITIVE_SAMPLE_TOKENS)
        )
        item = {
            "name": column_name,
            "dtype": str(series.dtype),
            "missing_count": int(missing[column]),
            "missing_rate": round(float(missing[column] / len(df)), 4) if len(df) else 0,
            "unique_count": int(series.nunique(dropna=True)),
            "sample_values": (
                []
                if redact_samples
                else [json_value(value) for value in series.dropna().unique()[:5]]
            ),
            "sample_values_redacted": redact_samples,
        }
        numeric = pd.to_numeric(series, errors="coerce")
        numeric_valid = numeric.dropna()
        if series.notna().sum() and len(numeric_valid) / series.notna().sum() >= 0.95:
            item["numeric"] = {
                "valid_count": int(numeric_valid.size),
                "invalid_count": int(series.notna().sum() - numeric_valid.size),
                "min": json_value(numeric_valid.min()),
                "median": json_value(numeric_valid.median()),
                "max": json_value(numeric_valid.max()),
                "negative_count": int((numeric_valid < 0).sum()),
                "zero_count": int((numeric_valid == 0).sum()),
            }
        columns.append(item)
    return {
        "rows": int(len(df)),
        "columns_count": int(len(df.columns)),
        "duplicate_rows": int(df.duplicated().sum()),
        "missing_cells": int(df.isna().sum().sum()),
        "columns": columns,
    }


def collect_issues(file_name: str, profile: dict) -> list[dict]:
    issues = []
    if profile["duplicate_rows"]:
        issues.append({
            "file": file_name,
            "type": "duplicate_rows",
            "severity": "check",
            "detail": f"완전 중복행 {profile['duplicate_rows']:,}건",
        })
    for column in profile["columns"]:
        name = column["name"]
        if name.startswith("Unnamed"):
            issues.append({
                "file": file_name,
                "type": "unnamed_column",
                "severity": "remove_candidate",
                "detail": (
                    f"{name}: 결측 {column['missing_count']:,}건, "
                    f"값 존재 {profile['rows'] - column['missing_count']:,}건"
                ),
            })
        elif column["missing_count"]:
            issues.append({
                "file": file_name,
                "type": "missing_values",
                "severity": "check",
                "detail": f"{name}: {column['missing_count']:,}건 ({column['missing_rate']:.1%})",
            })
        numeric = column.get("numeric")
        if numeric and numeric["negative_count"] and ("소요일" in name or "금액" in name or "비율" in name):
            issues.append({
                "file": file_name,
                "type": "negative_value",
                "severity": "definition_check",
                "detail": f"{name}: 음수 {numeric['negative_count']:,}건, 최소 {numeric['min']}",
            })
        if numeric and "비율" in name and (numeric["min"] < 0 or numeric["max"] > 300):
            issues.append({
                "file": file_name,
                "type": "ratio_outlier",
                "severity": "check",
                "detail": f"{name}: 범위 {numeric['min']}~{numeric['max']}",
            })
    return issues


def build_report(result: dict) -> str:
    lines = [
        "# 1단계 데이터 구조·품질 점검",
        "",
        "> 원본 파일은 수정하지 않았습니다. 이 단계에서는 분석 가능 여부와 정제 필요사항만 확인했습니다.",
        "",
        "## 파일 인벤토리",
        "",
        "| 파일 | 구분 | 행 | 열 | 중복행 | 결측 셀 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for file in result["files"]:
        for unit in file["units"]:
            profile = unit["profile"]
            label = "CSV" if unit["name"] == "CSV" else f"XLSX:{unit['name']}"
            lines.append(
                f"| {file['file']} | {label} | {profile['rows']:,} | {profile['columns_count']} | "
                f"{profile['duplicate_rows']:,} | {profile['missing_cells']:,} |"
            )
    lines.extend(["", "## 주요 품질 이슈", ""])
    for issue in result["issues"]:
        lines.append(f"- **{issue['file']}** - {issue['detail']}")
    lines.extend([
        "",
        "## 1단계 결론",
        "",
        "- 8개 파일 모두 정상적으로 읽혔습니다.",
        "- 원본을 그대로 수정하지 않고 다음 단계에서 표준화 사본을 만들어야 합니다.",
        "- 중복행은 식별키 확인 전 자동 삭제하지 않습니다.",
        "- 음수 소요일은 데이터정의서 확인 전 오류로 단정하거나 삭제하지 않습니다.",
        "- `시도명`·`시도구`처럼 상세주소가 들어 있는 컬럼은 행정구역을 별도로 추출해야 합니다.",
        "- `Unnamed` 컬럼은 내용 확인 후 제거 대상입니다.",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("analysis/01_data_quality"))
    args = parser.parse_args()

    result = {"source_directory": "provided_data", "files": [], "issues": []}
    for path in sorted(args.data_dir.iterdir()):
        if path.suffix.lower() not in {".csv", ".xlsx"}:
            continue
        file_result = {"file": path.name, "bytes": path.stat().st_size, "units": []}
        if path.suffix.lower() == ".csv":
            frame, encoding = read_csv_safe(path)
            profile = profile_frame(frame)
            file_result["encoding"] = encoding
            file_result["units"].append({"name": "CSV", "profile": profile})
            result["issues"].extend(collect_issues(path.name, profile))
        else:
            book = pd.ExcelFile(path)
            for sheet_name in book.sheet_names:
                frame = pd.read_excel(path, sheet_name=sheet_name)
                profile = profile_frame(frame)
                file_result["units"].append({"name": sheet_name, "profile": profile})
                if sheet_name == "비식별_상담데이터":
                    result["issues"].extend(collect_issues(f"{path.name}/{sheet_name}", profile))
        result["files"].append(file_result)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "inventory.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "report.md").write_text(build_report(result), encoding="utf-8")
    print(f"files: {len(result['files'])}")
    print(f"issues: {len(result['issues'])}")
    print(f"saved: {args.output_dir}")


if __name__ == "__main__":
    main()

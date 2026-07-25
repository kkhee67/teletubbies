"""Build deterministic demo outputs for the five mock properties."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scoring.service import analyze_sample  # noqa: E402


SAMPLE_CASES = [
    {"property_id": "MOCK-001", "planned_deposit": 200_000_000, "purpose": "근저당·보증 불가·미검증 참고가액"},
    {"property_id": "MOCK-002", "planned_deposit": 250_000_000, "purpose": "확인된 기본 흐름·보증 가입 완료"},
    {"property_id": "MOCK-003", "planned_deposit": 180_000_000, "purpose": "다가구·선순위 임차보증금 미확인"},
    {"property_id": "MOCK-004", "planned_deposit": 230_000_000, "purpose": "오피스텔 실제 용도·보증 추정만 존재"},
    {"property_id": "MOCK-005", "planned_deposit": 330_000_000, "purpose": "근저당 말소 약속·공동담보·보증 신청 중"},
]


def build_sample_results() -> list[dict]:
    return [
        {
            "input": case,
            "result": analyze_sample(case["property_id"], case["planned_deposit"]),
        }
        for case in SAMPLE_CASES
    ]


def main() -> None:
    output = ROOT / "backend/data/sample_analysis_results.json"
    output.write_text(
        json.dumps(build_sample_results(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"sample results: {len(SAMPLE_CASES)}")
    print(f"saved: {output}")


if __name__ == "__main__":
    main()

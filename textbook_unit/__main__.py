from __future__ import annotations

import argparse
from pathlib import Path

from .analyzer import analyze_unit


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a textbook unit PDF and enrich unit JSON.")
    parser.add_argument("textbook_pdf", type=Path)
    parser.add_argument("--unit-json", type=Path, default=Path("data/units/middle_school_informatics/unit_3.json"))
    parser.add_argument("--output-root", type=Path, default=Path("data/units/middle_school_informatics"))
    args = parser.parse_args()

    result = analyze_unit(args.textbook_pdf, args.unit_json, args.output_root)
    print("교과서 본문 분석을 완료했습니다.")
    print(f"- 페이지 수: {result['page_count']}")
    print(f"- 페이지별 텍스트: {result['page_dir']}")
    print(f"- 분석 JSON: {result['analysis_path']}")
    print(f"- 보강 JSON: {args.unit_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


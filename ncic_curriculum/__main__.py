from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import CurriculumError, approve_staging, import_to_staging, read_json, validate_curriculum


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ncic_curriculum",
        description="NCIC 2022 개정 중학교 정보 교육과정 수집·검토 도구",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="원문 PDF를 수집·구조화하여 staging에 저장")
    import_parser.add_argument(
        "source",
        nargs="?",
        help="로컬 PDF 또는 PDF/NCIC URL. 생략하면 NCIC에서 별책 10 PDF를 수집합니다.",
    )
    import_parser.add_argument("--data-dir", type=Path, default=Path("data/ncic"), help="결과 저장 폴더")

    approve_parser = subparsers.add_parser("approve", help="검토한 staging 데이터를 기준본으로 승인")
    approve_parser.add_argument("--data-dir", type=Path, default=Path("data/ncic"), help="결과 저장 폴더")

    validate_parser = subparsers.add_parser("validate", help="staging 또는 기준본의 구조와 누락 검사")
    validate_parser.add_argument("file", nargs="?", type=Path, help="검사할 JSON 파일")
    validate_parser.add_argument("--data-dir", type=Path, default=Path("data/ncic"), help="결과 저장 폴더")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "import":
            result = import_to_staging(args.source, args.data_dir)
            error_count = sum(issue["severity"] == "error" for issue in result["issues"])
            review_count = sum(issue["severity"] == "review" for issue in result["issues"])
            print("중학교 정보 교육과정 가져오기를 완료했습니다.")
            print(f"- 성취기준: {len(result['data']['achievement_standards'])}개")
            print(f"- 자동 검사: 오류 {error_count}건, 검토 필요 {review_count}건")
            for label, path in result["paths"].items():
                print(f"- {label}: {path}")
            return 2 if error_count else 0

        if args.command == "approve":
            paths = approve_staging(args.data_dir)
            print("검토본을 기준본으로 승인했습니다.")
            print(f"- current: {paths['current']}")
            print(f"- version: {paths['version']}")
            return 0

        path = args.file or args.data_dir / "staging" / "curriculum.json"
        data = read_json(path)
        if data is None:
            raise CurriculumError(f"검사할 JSON 파일이 없습니다: {path}")
        issues = validate_curriculum(data)
        print(json.dumps({"file": str(path), "issues": issues}, ensure_ascii=False, indent=2))
        return 2 if any(issue["severity"] == "error" for issue in issues) else 0
    except CurriculumError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

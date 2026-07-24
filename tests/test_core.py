import json
import tempfile
import unittest
from pathlib import Path

from ncic_curriculum.core import (
    AREA_NAMES,
    CurriculumError,
    approve_staging,
    compare_curricula,
    parse_achievement_standards,
    parse_content_system,
    validate_curriculum,
    write_json,
)


def sample_text() -> str:
    content_blocks = []
    standard_blocks = []
    counts = [3, 5, 9, 5, 3]
    for area_index, (area, count) in enumerate(zip(AREA_NAMES, counts), start=1):
        content_blocks.append(
            f"({area_index}) {area}"
            "핵심 아이디어•핵심 아이디어 하나•핵심 아이디어 둘"
            "구분범주 내용 요소중학교지식⋅이해•지식 요소"
            "과정⋅기능•과정 요소가치⋅태도•가치 요소"
        )
        definitions = "".join(
            f"[9정{area_index:02d}-{item:02d}] {area} 성취기준 {item}." for item in range(1, count + 1)
        )
        explanation = f"•[9정{area_index:02d}-01] {area} 첫 성취기준 해설."
        standard_blocks.append(
            f"({area_index}) {area}{definitions}"
            f"(가) 성취기준 해설{explanation}"
            "(나) 성취기준 적용 시 고려 사항•실생활 맥락을 활용한다."
        )
    return (
        "가. 내용 체계"
        + "".join(content_blocks)
        + "나. 성취기준"
        + "".join(standard_blocks)
        + "3. 교수⋅학습 및 평가"
    )


def valid_data() -> dict:
    text = sample_text()
    standards, areas = parse_achievement_standards(text)
    return {
        "metadata": {
            "notice_number": "교육부 고시 제2022-33호",
            "notice_date": "2022-12-22",
            "source_page_url": "https://ncic.re.kr/index.do",
            "collected_at": "2026-01-01T00:00:00+00:00",
            "source_sha256": "a" * 64,
        },
        "content_system": parse_content_system(text),
        "achievement_standard_areas": areas,
        "achievement_standards": standards,
        "teaching_learning": "교수학습 내용",
        "assessment": "평가 내용",
    }


class ParserTests(unittest.TestCase):
    def test_parses_five_content_areas(self):
        areas = parse_content_system(sample_text())
        self.assertEqual([item["area_name"] for item in areas], AREA_NAMES)
        self.assertTrue(all(item["core_ideas"] for item in areas))
        self.assertTrue(all(item["knowledge_understanding"] for item in areas))
        self.assertTrue(all(item["values_attitudes"] for item in areas))
        self.assertTrue(all(item["value_attitudes"] for item in areas))

    def test_normalizes_pdf_letter_spacing(self):
        text = (
            "가. 내용 체계"
            "(1) 컴퓨팅 시스템"
            "핵심 아이디어•컴 퓨 팅  시 스 템 을  설 계 하 는  것 은  중 요 하 다."
            "구분범주 내용 요소중학교지식⋅이해•지식 요소"
            "과정⋅기능•과정 요소가치⋅태도•가치 요소"
            "나. 성취기준"
        )
        area = parse_content_system(text)[0]
        self.assertEqual(area["core_ideas"][0], "컴퓨팅 시스템을 설계하는 것은 중요하다.")

    def test_parses_25_unique_standards(self):
        standards, areas = parse_achievement_standards(sample_text())
        self.assertEqual(len(standards), 25)
        self.assertEqual(len({item["id"] for item in standards}), 25)
        self.assertEqual(standards[0]["code"], "9정01-01")
        self.assertEqual(standards[-1]["code"], "9정05-03")
        self.assertEqual(len(areas), 5)

    def test_validation_accepts_complete_data(self):
        self.assertEqual(validate_curriculum(valid_data()), [])


class ChangeAndApprovalTests(unittest.TestCase):
    def test_compare_reports_only_modified_standard(self):
        previous = valid_data()
        current = json.loads(json.dumps(previous, ensure_ascii=False))
        current["achievement_standards"][0]["statement"] = "수정된 성취기준"
        changes = compare_curricula(previous, current)
        self.assertEqual(changes["summary"]["added"], 0)
        self.assertEqual(changes["summary"]["removed"], 0)
        self.assertEqual(changes["summary"]["modified"], 1)

    def test_approve_preserves_current_and_version(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            write_json(data_dir / "staging" / "curriculum.json", valid_data())
            paths = approve_staging(data_dir)
            self.assertTrue(Path(paths["current"]).exists())
            self.assertTrue(Path(paths["version"]).exists())

    def test_approve_blocks_invalid_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            data = valid_data()
            data["achievement_standards"] = []
            write_json(data_dir / "staging" / "curriculum.json", data)
            with self.assertRaises(CurriculumError):
                approve_staging(data_dir)


if __name__ == "__main__":
    unittest.main()

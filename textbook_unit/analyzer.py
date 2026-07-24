from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader


TEXTBOOK_PAGE_OFFSET = 73
SECTION_MARKERS = [
    ("01", "추상화와 알고리즘", 76),
    ("02", "프로그래밍", 96),
    ("03", "일상생활 문제 해결 프로그래밍", 124),
    ("04", "학문 분야 문제 해결 프로그래밍", 130),
    ("assessment", "대단원 평가", 134),
]
LESSON_MARKERS = [
    ("01-1", "문제의 추상화", 78, ["9정03-01", "9정03-02"]),
    ("01-2", "알고리즘의 표현과 설계", 84, ["9정03-02", "9정03-03", "9정03-04"]),
    ("02-1", "프로그래밍 시작하기", 98, ["9정03-05"]),
    ("02-2", "순차적인 데이터의 저장", 102, ["9정03-05"]),
    ("02-3", "논리 연산과 중첩 제어 구조", 108, ["9정03-06"]),
    ("02-4", "함수와 디버깅", 114, ["9정03-07"]),
    ("03", "일상생활 문제 해결 프로그래밍", 124, ["9정03-05", "9정03-06", "9정03-07", "9정03-08"]),
    ("04", "학문 분야 문제 해결 프로그래밍", 130, ["9정03-05", "9정03-06", "9정03-07", "9정03-09"]),
]
ACTIVITY_KEYWORDS = [
    "배움 열기",
    "생각 열기",
    "함께 해결하기",
    "해 보기",
    "활동",
        "실습",
        "따라 하는",
        "채워 보는",
        "스스로",
        "스스로 확인하기",
        "대단원 평가",
]


@dataclass(frozen=True)
class PageText:
    pdf_page: int
    textbook_page: int
    text: str


def clean_text(text: str) -> str:
    text = text.replace("\u0007", " ")
    text = text.replace("\u00a0", " ").replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", clean_text(text)).strip()


def extract_pages(pdf_path: Path) -> list[PageText]:
    reader = PdfReader(str(pdf_path))
    pages: list[PageText] = []
    for index, page in enumerate(reader.pages, start=1):
        text = clean_text(page.extract_text() or "")
        pages.append(PageText(pdf_page=index, textbook_page=index + TEXTBOOK_PAGE_OFFSET, text=text))
    return pages


def write_page_texts(pages: list[PageText], output_dir: Path) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for page in pages:
        path = output_dir / f"page_{page.textbook_page:03d}.txt"
        path.write_text(page.text + "\n", encoding="utf-8")
        paths.append(str(path))
    return paths


def page_index_for_textbook_page(textbook_page: int) -> int:
    return textbook_page - TEXTBOOK_PAGE_OFFSET - 1


def page_range_text(pages: list[PageText], start_textbook_page: int, end_textbook_page: int) -> str:
    start = max(page_index_for_textbook_page(start_textbook_page), 0)
    end = min(page_index_for_textbook_page(end_textbook_page), len(pages) - 1)
    return "\n".join(page.text for page in pages[start : end + 1])


def detect_keywords(text: str, keywords: list[str]) -> list[str]:
    compact_text = compact(text)
    return [keyword for keyword in keywords if keyword in compact_text]


def summarize_block(text: str) -> dict[str, Any]:
    lines = [compact(line) for line in text.splitlines() if compact(line)]
    goals = []
    for line in lines:
        if not line.endswith("수 있다."):
            continue
        if len(line) < 18 or line.startswith(("만 ", "을 ", "를 ", "에 ", "의 ")):
            continue
        if line not in goals:
            goals.append(line)
    keywords = detect_keywords(text, ACTIVITY_KEYWORDS)
    concept_candidates = []
    for line in lines:
        if line.startswith("#"):
            concept_candidates.extend([item.strip() for item in re.split(r"[#|]", line) if item.strip()])
        if len(concept_candidates) >= 8:
            break
    return {
        "detected_learning_goals": goals[:2],
        "detected_activity_keywords": keywords,
        "concept_candidates": concept_candidates[:8],
        "text_excerpt": compact(text)[:900],
    }


def build_section_analysis(pages: list[PageText]) -> dict[str, Any]:
    section_ranges = []
    for index, (code, title, start_page) in enumerate(SECTION_MARKERS):
        end_page = SECTION_MARKERS[index + 1][2] - 1 if index + 1 < len(SECTION_MARKERS) else 135
        section_ranges.append(
            {
                "section_number": code,
                "title": title,
                "textbook_page_start": start_page,
                "textbook_page_end": end_page,
                "summary": summarize_block(page_range_text(pages, start_page, end_page)),
            }
        )

    lessons = []
    for index, (lesson_id, title, start_page, codes) in enumerate(LESSON_MARKERS):
        if index + 1 < len(LESSON_MARKERS):
            end_page = min(LESSON_MARKERS[index + 1][2] - 1, 135)
        else:
            end_page = 133
        if lesson_id == "02-4":
            end_page = 117
        lessons.append(
            {
                "lesson_id": lesson_id,
                "title": title,
                "textbook_page_start": start_page,
                "textbook_page_end": end_page,
                "achievement_standard_codes": codes,
                "summary": summarize_block(page_range_text(pages, start_page, end_page)),
            }
        )

    return {
        "schema_version": "0.1",
        "generated_at": "2026-07-16",
        "page_mapping": {
            "pdf_page_1_textbook_page": TEXTBOOK_PAGE_OFFSET + 1,
            "textbook_page_offset": TEXTBOOK_PAGE_OFFSET,
        },
        "sections": section_ranges,
        "lessons": lessons,
    }


def merge_unit_analysis(unit_data: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    lesson_by_id = {item["lesson_id"]: item for item in analysis["lessons"]}
    section_by_id = {item["section_number"]: item for item in analysis["sections"]}
    for section in unit_data.get("sections", []):
        detected_section = section_by_id.get(section["section_number"])
        if detected_section:
            section["textbook_page_end"] = detected_section["textbook_page_end"]
            section["detected_activity_keywords"] = detected_section["summary"]["detected_activity_keywords"]
            section["text_excerpt"] = detected_section["summary"]["text_excerpt"]
        if "lessons" in section:
            for lesson in section["lessons"]:
                lesson_id = f"{section['section_number']}-{lesson['lesson_number']}"
                detected = lesson_by_id.get(lesson_id)
                if detected:
                    lesson["textbook_page_end"] = detected["textbook_page_end"]
                    lesson["detected_learning_goals"] = detected["summary"]["detected_learning_goals"]
                    lesson["detected_activity_keywords"] = detected["summary"]["detected_activity_keywords"]
                    lesson["concept_candidates"] = detected["summary"]["concept_candidates"]
                    lesson["text_excerpt"] = detected["summary"]["text_excerpt"]
        else:
            detected = lesson_by_id.get(section["section_number"])
            if detected:
                section["textbook_page_end"] = detected["textbook_page_end"]
                section["detected_learning_goals"] = detected["summary"]["detected_learning_goals"]
                section["detected_activity_keywords"] = detected["summary"]["detected_activity_keywords"]
                section["concept_candidates"] = detected["summary"]["concept_candidates"]
                section["text_excerpt"] = detected["summary"]["text_excerpt"]
    unit_data["analysis"] = {
        "status": "draft_from_pdf_text",
        "generated_at": analysis["generated_at"],
        "page_mapping": analysis["page_mapping"],
        "analysis_file": "data/units/middle_school_informatics/unit_3_analysis.json",
        "extracted_text_dir": "data/units/middle_school_informatics/unit_3_pages",
    }
    assessment = next((item for item in analysis["sections"] if item["section_number"] == "assessment"), None)
    if assessment and "assessment" in unit_data:
        unit_data["assessment"]["textbook_page_end"] = assessment["textbook_page_end"]
        unit_data["assessment"]["detected_activity_keywords"] = assessment["summary"]["detected_activity_keywords"]
        unit_data["assessment"]["text_excerpt"] = assessment["summary"]["text_excerpt"]
    return unit_data


def analyze_unit(textbook_pdf: Path, unit_json: Path, output_root: Path) -> dict[str, Any]:
    pages = extract_pages(textbook_pdf)
    page_dir = output_root / "unit_3_pages"
    page_paths = write_page_texts(pages, page_dir)
    analysis = build_section_analysis(pages)
    analysis["source_pdf"] = str(textbook_pdf)
    analysis["extracted_page_files"] = page_paths
    analysis_path = output_root / "unit_3_analysis.json"
    analysis_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    unit_data = json.loads(unit_json.read_text(encoding="utf-8"))
    unit_data = merge_unit_analysis(unit_data, analysis)
    unit_json.write_text(json.dumps(unit_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"analysis_path": str(analysis_path), "page_dir": str(page_dir), "page_count": len(pages)}

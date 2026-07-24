from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
import shutil
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader


DEFAULT_SEARCH_URL = (
    "https://www.ncic.re.kr/srch/result_more.do"
    "?search=%EA%B0%80%EC%A0%95&page=1&cate=attach"
)
NCIC_DOWNLOAD_URL = "https://www.ncic.re.kr/srch/download.do"
DEFAULT_SOURCE_PAGE = "https://ncic.re.kr/index.do"
DEFAULT_NOTICE_NUMBER = "교육부 고시 제2022-33호"
DEFAULT_NOTICE_DATE = "2022-12-22"
DEFAULT_EFFECTIVE_DATES = {
    "middle_school_grade_1": "2025-03-01",
    "middle_school_grade_2": "2026-03-01",
    "middle_school_grade_3": "2027-03-01",
}

AREA_NAMES = ["컴퓨팅 시스템", "데이터", "알고리즘과 프로그래밍", "인공지능", "디지털 문화"]
AREA_CODE = {
    "컴퓨팅 시스템": "01",
    "데이터": "02",
    "알고리즘과 프로그래밍": "03",
    "인공지능": "04",
    "디지털 문화": "05",
}


class CurriculumError(RuntimeError):
    """사용자가 조치할 수 있는 수집·추출 오류."""


@dataclass(frozen=True)
class DownloadCandidate:
    file_path: str
    file_name: str
    original_name: str
    file_id: str
    file_table: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _opener() -> urllib.request.OpenerDirector:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    opener.addheaders = [("User-Agent", "NCIC-Curriculum-Research/0.1 (manual collection)")]
    return opener


def _read_url(opener: urllib.request.OpenerDirector, url: str, data: bytes | None = None) -> tuple[bytes, str]:
    request = urllib.request.Request(url, data=data)
    try:
        with opener.open(request, timeout=60) as response:
            return response.read(), response.headers.get_content_type()
    except Exception as exc:  # urllib은 환경별 하위 예외가 다양하다.
        raise CurriculumError(f"원문을 가져오지 못했습니다: {url} ({exc})") from exc


def _parse_ncic_candidates(page: str) -> list[DownloadCandidate]:
    pattern = re.compile(
        r"file_down\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*\)"
    )
    candidates: list[DownloadCandidate] = []
    for match in pattern.finditer(page):
        values = [html.unescape(value.replace("<!HS>", "").replace("<!HE>", "")) for value in match.groups()]
        candidate = DownloadCandidate(*values)
        normalized = candidate.original_name.replace(" ", "")
        if "별책10" in normalized and "정보과교육과정" in normalized and candidate.file_name.lower().endswith(".pdf"):
            candidates.append(candidate)
    return candidates


def download_ncic_pdf(search_url: str = DEFAULT_SEARCH_URL) -> tuple[bytes, dict[str, str]]:
    """NCIC 검색 화면의 정상 다운로드 폼을 이용해 별책 10 PDF를 한 번 내려받는다."""
    opener = _opener()
    page_bytes, _ = _read_url(opener, search_url)
    page = page_bytes.decode("utf-8", errors="replace")
    csrf_match = re.search(r'name="_csrf"\s+value="([^"]+)"', page)
    candidates = _parse_ncic_candidates(page)
    if not csrf_match:
        raise CurriculumError("NCIC 다운로드 페이지에서 CSRF 토큰을 찾지 못했습니다.")
    if not candidates:
        raise CurriculumError("NCIC 검색 결과에서 별책 10 PDF를 찾지 못했습니다.")

    # NCIC 검색 결과는 최신 개정 자료를 먼저 제공한다. 다운로드 뒤 고시 번호를 다시 검증한다.
    candidate = candidates[0]
    form = urllib.parse.urlencode(
        {
            "_csrf": csrf_match.group(1),
            "filePath": candidate.file_path,
            "fileName": candidate.file_name,
            "fileOrg": candidate.original_name,
            "fileIdx": candidate.file_id,
            "fileTbl": candidate.file_table,
        }
    ).encode("utf-8")
    pdf, content_type = _read_url(opener, NCIC_DOWNLOAD_URL, form)
    if not pdf.startswith(b"%PDF"):
        raise CurriculumError(f"NCIC 응답이 PDF가 아닙니다(content-type: {content_type}).")
    return pdf, {
        "source_page_url": search_url,
        "download_url": NCIC_DOWNLOAD_URL,
        "original_filename": candidate.original_name,
        "ncic_file_id": candidate.file_id,
    }


def download_direct_pdf(url: str) -> tuple[bytes, dict[str, str]]:
    data, content_type = _read_url(_opener(), url)
    if not data.startswith(b"%PDF"):
        raise CurriculumError(f"입력 URL의 응답이 PDF가 아닙니다(content-type: {content_type}).")
    name = Path(urllib.parse.urlparse(url).path).name or "curriculum.pdf"
    return data, {"source_page_url": url, "download_url": url, "original_filename": name}


def acquire_pdf(source: str | Path | None) -> tuple[bytes, dict[str, str]]:
    if source is None:
        return download_ncic_pdf()
    source_text = str(source)
    if re.match(r"https?://", source_text):
        if "ncic.re.kr/index.do" in source_text or "ncic.re.kr/srch/" in source_text:
            return download_ncic_pdf(DEFAULT_SEARCH_URL if "index.do" in source_text else source_text)
        return download_direct_pdf(source_text)
    path = Path(source_text)
    if not path.exists():
        raise CurriculumError(f"입력 파일이 없습니다: {path}")
    if path.suffix.lower() != ".pdf":
        raise CurriculumError("현재 시범 버전은 PDF만 지원합니다. HWP는 같은 내용의 PDF로 바꾸어 입력하세요.")
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise CurriculumError("입력 파일이 올바른 PDF가 아닙니다.")
    return data, {
        "source_page_url": str(path.resolve()),
        "download_url": "",
        "original_filename": path.name,
    }


def _clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", _clean_text(text)).strip()


def _strip_page_furniture(text: str) -> str:
    lines = []
    for line in text.splitlines():
        value = line.strip()
        if value in {"실과(기술⋅가정)/정보과 교육과정", "공통 교육과정 – 정보 -", "공통 교육과정- 정보 -"}:
            continue
        if re.fullmatch(r"\d{1,3}", value):
            continue
        lines.append(line)
    return "\n".join(lines)


def extract_middle_school_pages(pdf: bytes) -> tuple[str, list[int], int]:
    reader = PdfReader(io.BytesIO(pdf))
    pages = [page.extract_text() or "" for page in reader.pages]
    start = None
    for index, text in enumerate(pages):
        compact = _compact(text)
        if (
            ("공통 교육과정 – 정보 -" in text or "공통 교육과정- 정보 -" in text)
            and "정보 교육과정 설계의 개요" in compact
        ):
            start = index
            break
    if start is None:
        # 일부 PDF는 머리말의 대시 문자를 다르게 추출한다.
        for index, text in enumerate(pages):
            compact = _compact(text)
            if (
                "정보 교육과정 설계의 개요" in compact
                and "컴퓨팅 사고력" in compact
                and index > len(pages) // 2
            ):
                start = index
                break
    if start is None:
        raise CurriculumError("PDF에서 중학교 정보 교육과정의 시작 부분을 찾지 못했습니다.")

    end = None
    for index in range(start + 1, len(pages)):
        compact = _compact(pages[index])
        if compact.startswith("선택 중심 교육과정") and "159" in compact[:30]:
            end = index
            break
    if end is None:
        for index in range(start + 1, len(pages)):
            if "선택 중심 교육과정" in _compact(pages[index]) and "3. 교수⋅학습 및 평가" not in _compact(pages[index]):
                end = index
                break
    if end is None:
        raise CurriculumError("PDF에서 중학교 정보 교육과정의 끝 부분을 찾지 못했습니다.")

    selected_indexes = list(range(start, end))
    text = "\n".join(_strip_page_furniture(pages[index]) for index in selected_indexes)
    text = text.replace("\u00a0", " ").replace("\r", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(), [index + 1 for index in selected_indexes], len(reader.pages)


def _between(text: str, start: str, end: str | None = None) -> str:
    start_index = text.find(start)
    if start_index < 0:
        return ""
    start_index += len(start)
    if end is None:
        return text[start_index:].strip()
    end_index = text.find(end, start_index)
    return text[start_index : end_index if end_index >= 0 else None].strip()


def _split_bullets(text: str) -> list[str]:
    items = [_compact(_normalize_pdf_spacing(item)) for item in re.split(r"[•Ÿ⋅]\s*", text) if _compact(item)]
    return items


def _normalize_pdf_spacing(text: str) -> str:
    """Join Hangul syllables that PDF table extraction separated one by one."""

    word_boundary = "\ue000"
    text = re.sub(r"(?<=[가-힣])\s{2,}(?=[가-힣])", word_boundary, text)

    def join_letter_spaced(match: re.Match[str]) -> str:
        return re.sub(r"\s+", "", match.group(0))

    text = re.sub(r"(?<![가-힣])(?:[가-힣]\s){1,}[가-힣](?![가-힣])", join_letter_spaced, text)
    return text.replace(word_boundary, " ")


def _area_blocks(text: str, end_marker: str) -> list[tuple[str, str]]:
    positions: list[tuple[int, str]] = []
    for index, name in enumerate(AREA_NAMES, start=1):
        match = re.search(rf"\({index}\)\s*{re.escape(name)}", text)
        if match:
            positions.append((match.start(), name))
    blocks: list[tuple[str, str]] = []
    end_position = text.find(end_marker)
    if end_position < 0:
        end_position = len(text)
    for idx, (position, name) in enumerate(positions):
        next_position = positions[idx + 1][0] if idx + 1 < len(positions) else end_position
        blocks.append((name, text[position:next_position].strip()))
    return blocks


def parse_content_system(text: str) -> list[dict[str, Any]]:
    section = _between(text, "가. 내용 체계", "나. 성취기준")
    result: list[dict[str, Any]] = []
    for name, block in _area_blocks(section, "나. 성취기준"):
        core = _between(block, "핵심 아이디어", "구분범주 내용 요소")
        table = _between(block, "구분범주 내용 요소")
        knowledge = _between(table, "중학교지식⋅이해", "과정⋅기능")
        process = _between(table, "과정⋅기능", "가치⋅태도")
        values = _between(table, "가치⋅태도")
        values_attitudes = _split_bullets(values)
        result.append(
            {
                "area_code": AREA_CODE[name],
                "area_name": name,
                "core_ideas": _split_bullets(core),
                "knowledge_understanding": _split_bullets(knowledge),
                "process_skills": _split_bullets(process),
                "values_attitudes": values_attitudes,
                "value_attitudes": values_attitudes,
                "raw_text": _compact(block),
            }
        )
    return result


def _parse_coded_items(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"[•Ÿ]?\s*\[(9정\d{2}-\d{2})\]\s*", text))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = _compact(text[match.end() : end]).lstrip("•Ÿ ")
        result[match.group(1)] = value
    return result


def parse_achievement_standards(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    section = _between(text, "나. 성취기준", "3. 교수⋅학습 및 평가")
    standards: list[dict[str, Any]] = []
    areas: list[dict[str, Any]] = []
    for area_name, block in _area_blocks(section, "3. 교수⋅학습 및 평가"):
        explanation_marker = "(가) 성취기준 해설"
        consideration_marker = "(나) 성취기준 적용 시 고려 사항"
        definitions_text = block.split(explanation_marker, 1)[0]
        explanations_text = _between(block, explanation_marker, consideration_marker)
        considerations_text = _between(block, consideration_marker)
        definitions = _parse_coded_items(definitions_text)
        explanations = _parse_coded_items(explanations_text)
        considerations = _split_bullets(considerations_text)
        area_standard_ids: list[str] = []
        for code, statement in definitions.items():
            identifier = f"2022-middle-informatics-{code}"
            area_standard_ids.append(identifier)
            standards.append(
                {
                    "id": identifier,
                    "code": code,
                    "area_code": AREA_CODE[area_name],
                    "area_name": area_name,
                    "statement": statement,
                    "explanation": explanations.get(code, ""),
                    "considerations": considerations,
                }
            )
        areas.append(
            {
                "area_code": AREA_CODE[area_name],
                "area_name": area_name,
                "achievement_standard_ids": area_standard_ids,
                "considerations": considerations,
            }
        )
    return standards, areas


def parse_curriculum(pdf: bytes, source_metadata: dict[str, str]) -> dict[str, Any]:
    text, page_numbers, page_count = extract_middle_school_pages(pdf)
    if DEFAULT_NOTICE_NUMBER not in _compact(" ".join(PdfReader(io.BytesIO(pdf)).pages[0].extract_text() or "" for _ in [0])):
        # 표지 추출이 빈 문서도 있으므로 전체 선택 본문에서 다시 확인한다.
        first_page = PdfReader(io.BytesIO(pdf)).pages[0].extract_text() or ""
        if "2022-33" not in first_page:
            raise CurriculumError("교육부 고시 제2022-33호 별책 10 PDF인지 확인할 수 없습니다.")

    overview = _between(text, "정보 교육과정 설계의 개요", "1. 성격 및 목표")
    nature = _between(text, "가. 성격", "나. 목표")
    goals_section = _between(text, "나. 목표", "2. 내용 체계 및 성취기준")
    overall_goal_match = re.match(r"(.+?)(?=\(1\))", _compact(goals_section))
    detailed_goals = [
        _compact(match.group(1))
        for match in re.finditer(r"\(\d\)\s*(.*?)(?=\(\d\)|$)", _compact(goals_section))
    ]
    content_system = parse_content_system(text)
    standards, standard_areas = parse_achievement_standards(text)
    pedagogy = _between(text, "가. 교수⋅학습", "나. 평가")
    assessment = _between(text, "나. 평가")
    collected_at = utc_now()

    metadata = {
        "schema_version": "1.0",
        "curriculum_revision": "2022 개정 교육과정",
        "notice_number": DEFAULT_NOTICE_NUMBER,
        "notice_date": DEFAULT_NOTICE_DATE,
        "effective_dates": DEFAULT_EFFECTIVE_DATES,
        "school_level": "중학교",
        "subject": "정보",
        "source_title": "[별책 10] 실과(기술⋅가정)/정보과 교육과정",
        "source_page_url": source_metadata.get("source_page_url", DEFAULT_SOURCE_PAGE),
        "download_url": source_metadata.get("download_url", ""),
        "original_filename": source_metadata.get("original_filename", "curriculum.pdf"),
        "ncic_file_id": source_metadata.get("ncic_file_id", ""),
        "collected_at": collected_at,
        "source_sha256": sha256_bytes(pdf),
        "source_page_count": page_count,
        "extracted_pdf_pages": page_numbers,
        "license_note": "비영리 연구용. NCIC 및 원문에 표시된 이용 조건과 출처 표시 의무를 확인할 것.",
    }
    return {
        "metadata": metadata,
        "identity": {"school_level": "중학교", "subject": "정보", "grade_band": "중학교 1~3학년"},
        "competencies": ["컴퓨팅 사고력", "디지털 문화 소양", "인공지능 소양"],
        "design_overview": _compact(overview),
        "nature": _compact(nature),
        "goals": {
            "overall": overall_goal_match.group(1).strip() if overall_goal_match else "",
            "details": detailed_goals,
        },
        "content_system": content_system,
        "achievement_standard_areas": standard_areas,
        "achievement_standards": standards,
        "teaching_learning": _compact(pedagogy),
        "assessment": _compact(assessment),
        "raw_extracted_text": text,
    }


def validate_curriculum(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    def add(severity: str, code: str, message: str, context: str = "") -> None:
        issues.append({"severity": severity, "code": code, "message": message, "context": context})

    metadata = data.get("metadata", {})
    for key in ("notice_number", "notice_date", "source_page_url", "collected_at", "source_sha256"):
        if not metadata.get(key):
            add("error", "missing_metadata", f"필수 출처 정보가 없습니다: {key}", key)

    systems = data.get("content_system", [])
    if [item.get("area_name") for item in systems] != AREA_NAMES:
        add("error", "content_areas", "내용 체계의 5개 영역을 정확히 추출하지 못했습니다.")
    for item in systems:
        for key in ("core_ideas", "knowledge_understanding", "process_skills", "values_attitudes"):
            if not item.get(key):
                add("review", "empty_content_field", f"내용 체계 항목이 비어 있습니다: {item.get('area_name')} / {key}")
        structured_text = " ".join(
            " ".join(item.get(key, []))
            for key in ("core_ideas", "knowledge_understanding", "process_skills", "values_attitudes")
        )
        if re.search(r"(?:[가-힣]\s+){4,}[가-힣]", structured_text):
            add(
                "review",
                "pdf_letter_spacing",
                f"PDF 표의 글자 간격을 원문과 대조해야 합니다: {item.get('area_name')}",
                item.get("area_name", ""),
            )

    standards = data.get("achievement_standards", [])
    if len(standards) != 25:
        add("error", "standard_count", f"성취기준은 25개여야 하지만 {len(standards)}개를 추출했습니다.")
    codes = [item.get("code", "") for item in standards]
    if len(codes) != len(set(codes)):
        add("error", "duplicate_standard", "중복된 성취기준 코드가 있습니다.")
    for item in standards:
        code = item.get("code", "")
        if not re.fullmatch(r"9정\d{2}-\d{2}", code):
            add("error", "invalid_standard_code", f"성취기준 코드 형식이 잘못되었습니다: {code}", code)
        if not item.get("statement"):
            add("error", "empty_standard", f"성취기준 본문이 없습니다: {code}", code)
        if not item.get("id", "").endswith(code):
            add("error", "invalid_standard_id", f"성취기준 고유 식별자가 잘못되었습니다: {code}", code)

    if not data.get("teaching_learning"):
        add("error", "missing_pedagogy", "교수⋅학습 방향과 방법을 추출하지 못했습니다.")
    if not data.get("assessment"):
        add("error", "missing_assessment", "평가 방향과 방법을 추출하지 못했습니다.")
    return issues


def _canonical_standard(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item.get(key) for key in ("id", "code", "area_code", "area_name", "statement", "explanation", "considerations")}


def compare_curricula(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    before = {item["id"]: _canonical_standard(item) for item in (previous or {}).get("achievement_standards", [])}
    after = {item["id"]: _canonical_standard(item) for item in current.get("achievement_standards", [])}
    added = [after[key] for key in sorted(after.keys() - before.keys())]
    removed = [before[key] for key in sorted(before.keys() - after.keys())]
    modified = [
        {"id": key, "before": before[key], "after": after[key]}
        for key in sorted(before.keys() & after.keys())
        if before[key] != after[key]
    ]
    previous_content = (previous or {}).get("content_system", [])
    content_changed = previous is not None and previous_content != current.get("content_system", [])
    return {
        "generated_at": utc_now(),
        "previous_source_sha256": (previous or {}).get("metadata", {}).get("source_sha256", ""),
        "current_source_sha256": current.get("metadata", {}).get("source_sha256", ""),
        "summary": {
            "added": len(added),
            "modified": len(modified),
            "removed": len(removed),
            "content_system_changed": content_changed,
        },
        "added": added,
        "modified": modified,
        "removed": removed,
    }


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def write_review_csv(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", dir=path.parent, delete=False, suffix=".tmp") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["검토 상태", "영역", "성취기준 코드", "성취기준", "해설", "적용 시 고려 사항", "고유 식별자"],
        )
        writer.writeheader()
        for item in data.get("achievement_standards", []):
            writer.writerow(
                {
                    "검토 상태": "미검토",
                    "영역": item["area_name"],
                    "성취기준 코드": item["code"],
                    "성취기준": item["statement"],
                    "해설": item["explanation"],
                    "적용 시 고려 사항": " / ".join(item["considerations"]),
                    "고유 식별자": item["id"],
                }
            )
        temp_path = Path(handle.name)
    temp_path.replace(path)


def import_to_staging(source: str | Path | None, data_dir: Path) -> dict[str, Any]:
    pdf, source_metadata = acquire_pdf(source)
    data = parse_curriculum(pdf, source_metadata)
    issues = validate_curriculum(data)

    raw_dir = data_dir / "raw"
    staging_dir = data_dir / "staging"
    reports_dir = data_dir / "reports"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"book10_{data['metadata']['source_sha256'][:12]}.pdf"
    if not raw_path.exists():
        raw_path.write_bytes(pdf)
    data["metadata"]["local_source_file"] = str(raw_path)

    current = read_json(data_dir / "approved" / "current.json")
    changes = compare_curricula(current, data)
    write_json(staging_dir / "curriculum.json", data)
    write_json(reports_dir / "changes.json", changes)
    write_json(reports_dir / "errors.json", {"generated_at": utc_now(), "issues": issues})
    write_review_csv(reports_dir / "review.csv", data)
    return {
        "data": data,
        "issues": issues,
        "changes": changes,
        "paths": {
            "staging": str(staging_dir / "curriculum.json"),
            "review": str(reports_dir / "review.csv"),
            "changes": str(reports_dir / "changes.json"),
            "errors": str(reports_dir / "errors.json"),
            "raw": str(raw_path),
        },
    }


def approve_staging(data_dir: Path) -> dict[str, str]:
    staging_path = data_dir / "staging" / "curriculum.json"
    data = read_json(staging_path)
    if data is None:
        raise CurriculumError("승인할 staging/curriculum.json이 없습니다. 먼저 import를 실행하세요.")
    issues = validate_curriculum(data)
    blocking = [issue for issue in issues if issue["severity"] == "error"]
    if blocking:
        raise CurriculumError(f"오류 {len(blocking)}건이 있어 승인할 수 없습니다. reports/errors.json을 확인하세요.")
    approved_dir = data_dir / "approved"
    version_dir = approved_dir / "versions"
    version_name = f"{data['metadata']['notice_date']}_{data['metadata']['source_sha256'][:12]}.json"
    write_json(version_dir / version_name, data)
    write_json(approved_dir / "current.json", data)
    return {"current": str(approved_dir / "current.json"), "version": str(version_dir / version_name)}


def copy_example_pdf(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)

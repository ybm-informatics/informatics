from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_lesson(unit: dict[str, Any], section_number: str, lesson_number: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for section in unit["sections"]:
        if section["section_number"] != section_number:
            continue
        for lesson in section.get("lessons", []):
            if lesson["lesson_number"] == lesson_number:
                return section, lesson
    raise ValueError(f"Lesson not found: {section_number}-{lesson_number}")


def build_plan(unit: dict[str, Any], rules: dict[str, Any], section_number: str, lesson_number: str) -> dict[str, Any]:
    section, lesson = find_lesson(unit, section_number, lesson_number)
    goals = lesson.get("detected_learning_goals") or lesson.get("draft_learning_goals", [])
    goals = goals[: rules["learning_goal_rules"]["count"]]
    textbook_pages = f"교과서 {lesson['textbook_page_start']}~{lesson['textbook_page_end']}쪽"
    lesson_title = f"{section_number}-{lesson_number}. {lesson['title']}"

    return {
        "schema_version": "0.1",
        "created_at": "2026-07-16",
        "status": "draft",
        "document_type": "교수·학습 과정안",
        "unit_title": f"{unit['unit']['unit_number']}. {unit['unit']['title']}",
        "section_title": section["title"],
        "lesson_title": lesson_title,
        "period": "차시 미정 / 68차시",
        "textbook_pages": textbook_pages,
        "achievement_standard_codes": lesson["achievement_standard_codes"],
        "learning_goals": goals,
        "teaching_learning_methods": ["강의", "탐구 활동", "개별 활동", "발표"],
        "assessment_methods": ["자기 평가", "관찰 평가"],
        "materials": {
            "teacher": ["교과서", "프레젠테이션 자료", "활동 예시 자료"],
            "student": ["교과서", "필기도구"],
        },
        "lesson_flow": [
            {
                "stage": "도입",
                "learning_elements": ["학습 목표 확인", "생각 열기"],
                "teaching_learning_activities": [
                    "학습 목표를 소개한다.",
                    "‘일곱 마리 아기 염소’ 이야기에서 늑대와 엄마를 구분할 수 있었던 핵심 특징을 떠올리게 한다.",
                    "복잡한 상황에서 문제 해결에 필요한 핵심 요소를 찾는 과정이 추상화와 연결됨을 안내한다.",
                ],
                "teaching_notes": [
                    "학생이 이야기의 세부 내용보다 핵심 특징을 찾는 데 집중하도록 발문한다.",
                    "추상화를 단순한 생략이 아니라 문제 해결에 필요한 요소를 뽑는 과정으로 이해하도록 한다.",
                ],
            },
            {
                "stage": "전개",
                "learning_elements": ["문제", "문제 추상화", "문제의 상태와 구조화", "추상화의 중요성"],
                "teaching_learning_activities": [
                    "➊ 문제와 문제 해결",
                    "• 문제의 의미를 안내한다.",
                    "• 컴퓨팅 시스템을 활용한 문제 해결 과정이 문제 이해와 추상화, 문제 해결 방법 설계, 문제 해결 방법 실행, 문제 해결 방법 평가의 흐름으로 이루어짐을 안내한다.",
                    "• 우리 주변의 다양한 문제를 떠올리고 해결하고 싶은 문제를 적어 보도록 한다.",
                    "스스로 탐색: 우리 주변의 다양한 문제",
                    "➋ 문제의 상태와 구조화",
                    "• 초기 상태, 현재 상태, 목표 상태의 의미를 숨은그림찾기 예시와 연결하여 안내한다.",
                    "• 산불 문제 사례를 활용하여 문제 상황을 자료로 구조화하는 방법을 설명한다.",
                    "➌ 추상화의 중요성",
                    "• 추상화는 복잡한 문제에서 핵심 요소를 추출하여 간략하게 나타내는 과정임을 안내한다.",
                    "• 친구 관계 문제를 그림으로 구조화하고, 글과 그림 중 어떤 표현이 문제 해결에 효율적인지 비교하게 한다.",
                    "스스로 표현: 문제의 구조화와 추상화",
                ],
                "teaching_notes": [
                    "초기 상태, 현재 상태, 목표 상태를 구분하지 못하는 학생에게 구체적인 생활 사례를 추가로 제시한다.",
                    "구조화 활동에서는 정답보다 문제를 단순하고 명확하게 표현하는 과정에 초점을 둔다.",
                    "친구 관계 문제는 협력적으로 의견을 나누되, 판단 근거를 말로 설명하게 한다.",
                ],
            },
            {
                "stage": "정리 및 평가",
                "learning_elements": ["학습 내용 정리", "자기 평가", "차시 예고"],
                "teaching_learning_activities": [
                    "문제, 문제 상태, 구조화, 추상화의 관계를 정리한다.",
                    "학생이 자신의 문제 구조화 결과를 점검하고, 추상화의 중요성을 설명하게 한다.",
                    "다음 차시에서 알고리즘의 표현과 설계로 이어짐을 안내한다.",
                ],
                "teaching_notes": [
                    "평가 시 결과물의 미려함보다 문제 상태 정의와 핵심 요소 추출 여부를 중점적으로 확인한다.",
                    "차시 예고에서 구조화한 문제를 알고리즘으로 표현하는 흐름을 연결한다.",
                ],
            },
        ],
        "source": {
            "unit_json": "data/units/middle_school_informatics/unit_3.json",
            "template_rules": "data/templates/teaching_plan/middle_school_informatics_rules.json",
            "text_excerpt": lesson.get("text_excerpt", ""),
        },
        "review_notes": [
            "차시 번호는 현재 미정으로 두었다. 실제 연간 지도 계획에 맞춰 조정이 필요하다.",
            "본문 기반 초안이므로 편집자가 활동 시간, 수업 자료명, 평가 문항을 검토해야 한다.",
        ],
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        f"# {plan['lesson_title']} 교수·학습 과정안",
        "",
        f"- 단원: {plan['unit_title']}",
        f"- 소단원: {plan['section_title']}",
        f"- 차시: {plan['period']}",
        f"- 쪽수: {plan['textbook_pages']}",
        f"- 성취기준: {', '.join(plan['achievement_standard_codes'])}",
        "",
        "## 학습 목표",
        "",
    ]
    lines.extend(f"- {goal}" for goal in plan["learning_goals"])
    lines.extend(
        [
            "",
            "## 교수·학습 및 평가 방법",
            "",
            f"- 교수·학습: {', '.join(plan['teaching_learning_methods'])}",
            f"- 평가: {', '.join(plan['assessment_methods'])}",
            "",
            "## 준비물",
            "",
            f"- 교사: {', '.join(plan['materials']['teacher'])}",
            f"- 학생: {', '.join(plan['materials']['student'])}",
            "",
            "## 교수·학습 과정",
            "",
            "| 단계 | 학습 요소 | 교수·학습 활동 | 지도상의 유의점 |",
            "|---|---|---|---|",
        ]
    )
    for item in plan["lesson_flow"]:
        activities = "<br>".join(f"- {activity}" for activity in item["teaching_learning_activities"])
        notes = "<br>".join(f"- {note}" for note in item["teaching_notes"])
        elements = "<br>".join(item["learning_elements"])
        lines.append(f"| {item['stage']} | {elements} | {activities} | {notes} |")
    lines.extend(["", "## 검토 메모", ""])
    lines.extend(f"- {note}" for note in plan["review_notes"])
    lines.append("")
    return "\n".join(lines)


def generate(output_dir: Path, section_number: str, lesson_number: str) -> dict[str, str]:
    unit = load_json(Path("data/units/middle_school_informatics/unit_3.json"))
    rules = load_json(Path("data/templates/teaching_plan/middle_school_informatics_rules.json"))
    plan = build_plan(unit, rules, section_number, lesson_number)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"unit_3_{section_number}_{lesson_number}_teaching_plan_draft"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(plan), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a draft teaching-learning plan.")
    parser.add_argument("--section", default="01")
    parser.add_argument("--lesson", default="1")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/teaching_plans"))
    args = parser.parse_args()
    paths = generate(args.output_dir, args.section, args.lesson)
    print("교수학습과정안 초안을 생성했습니다.")
    print(f"- JSON: {paths['json']}")
    print(f"- Markdown: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

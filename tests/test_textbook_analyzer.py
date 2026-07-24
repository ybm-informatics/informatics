import unittest

from textbook_unit.analyzer import summarize_block


class TextbookAnalyzerTests(unittest.TestCase):
    def test_summarize_block_deduplicates_and_filters_goal_fragments(self):
        summary = summarize_block(
            "\n".join(
                [
                    "만 저장할 수 있는 변수에 비해 많은 양의 데이터를 저장할 수 있다.",
                    "문제를 구조화하여 해결할 수 있다.",
                    "문제를 구조화하여 해결할 수 있다.",
                    "생각 열기",
                    "# 문제 | # 추상화",
                ]
            )
        )

        self.assertEqual(summary["detected_learning_goals"], ["문제를 구조화하여 해결할 수 있다."])
        self.assertIn("생각 열기", summary["detected_activity_keywords"])
        self.assertEqual(summary["concept_candidates"], ["문제", "추상화"])


if __name__ == "__main__":
    unittest.main()


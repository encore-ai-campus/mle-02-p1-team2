import unittest

from src.sif_rag.evaluate import evaluate


DOCUMENTS = [{"case_id": "SIF-1", "page_content": "forklift fall incident", "fields": {}}]


class EvaluateTests(unittest.TestCase):
    def test_reports_metrics_for_complete_legacy_label_set(self):
        result = evaluate(
            [{"id": "q001", "question": "forklift", "expected_case_ids": ["SIF-1"]}],
            DOCUMENTS,
            k=1,
        )
        self.assertEqual(result["labeled_questions"], 1)
        self.assertEqual(result["hit_rate_at_1"], 1.0)

    def test_refuses_to_score_partial_label_set(self):
        questions = [
            {"id": "q001", "question": "forklift", "expected_case_ids": ["SIF-1"]},
            {"id": "q002", "question": "fall", "expected_case_ids": []},
        ]
        with self.assertRaisesRegex(ValueError, "Refusing partial evaluation: 1 of 2"):
            evaluate(questions, DOCUMENTS, k=1)

    def test_refuses_questions_not_marked_human_gold(self):
        questions = [{
            "id": "q001", "question": "forklift", "expected_case_ids": ["SIF-1"],
            "status": "needs_label",
        }]
        with self.assertRaisesRegex(ValueError, "not marked human_gold"):
            evaluate(questions, DOCUMENTS, k=1)

    def test_allows_explicit_human_gold_question(self):
        questions = [{
            "id": "q001", "question": "forklift", "expected_case_ids": ["SIF-1"],
            "status": "human_gold", "reviewer": "reviewer_A",
        }]
        self.assertEqual(evaluate(questions, DOCUMENTS, k=1)["labeled_questions"], 1)


if __name__ == "__main__":
    unittest.main()

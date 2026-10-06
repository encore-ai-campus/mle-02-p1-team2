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

    def test_rejects_assistant_reviewer_even_when_status_claims_human_gold(self):
        questions = [{
            "id": "q001", "question": "forklift", "expected_case_ids": ["SIF-1"],
            "status": "human_gold", "reviewer": "assistant_second_pass",
        }]
        with self.assertRaisesRegex(ValueError, "valid human reviewer"):
            evaluate(questions, DOCUMENTS, k=1)

    def test_rejects_human_gold_without_reviewer(self):
        questions = [{
            "id": "q001", "question": "forklift", "expected_case_ids": ["SIF-1"],
            "status": "human_gold",
        }]
        with self.assertRaisesRegex(ValueError, "valid human reviewer"):
            evaluate(questions, DOCUMENTS, k=1)

    def test_rejects_duplicate_question_ids(self):
        question = {"id": "q001", "question": "forklift", "expected_case_ids": ["SIF-1"]}
        with self.assertRaisesRegex(ValueError, "Duplicate question IDs"):
            evaluate([question, dict(question)], DOCUMENTS, k=1)

    def test_rejects_duplicate_expected_case_ids(self):
        question = {"id": "q001", "question": "forklift", "expected_case_ids": ["SIF-1", " SIF-1 "]}
        with self.assertRaisesRegex(ValueError, "duplicate expected_case_ids"):
            evaluate([question], DOCUMENTS, k=1)

    def test_rejects_invalid_k(self):
        question = {"id": "q001", "question": "forklift", "expected_case_ids": ["SIF-1"]}
        for invalid in (0, -1, True, 1.5):
            with self.subTest(k=invalid), self.assertRaisesRegex(ValueError, "positive integer"):
                evaluate([question], DOCUMENTS, k=invalid)



def ai_judgment(case_id, label, **updates):
    value = {
        "case_id": case_id,
        "label": label,
        "annotator": "AI provisional",
        "model_version": "test-model-v1",
        "evidence_ref": f"{case_id}:disasterFactor",
        "rationale": "The source mechanism was compared with the query.",
        "confidence": "medium",
    }
    value.update(updates)
    return value


class AIProvisionalEvaluateTests(unittest.TestCase):
    def test_requires_explicit_opt_in(self):
        question = {
            "id": "q001",
            "question": "forklift",
            "status": "ai_provisional",
            "judgments": [ai_judgment("SIF-1", "relevant")],
        }
        with self.assertRaisesRegex(ValueError, "require --allow-ai-provisional"):
            evaluate([question], DOCUMENTS, k=1)

    def test_reports_provisional_metrics_and_uncertainty_bounds(self):
        documents = [
            {"case_id": "SIF-U", "page_content": "forklift forklift forklift forklift", "fields": {}},
            {"case_id": "SIF-1", "page_content": "forklift", "fields": {}},
        ]
        question = {
            "id": "q001",
            "question": "forklift",
            "status": "ai_provisional",
            "judgments": [
                ai_judgment("SIF-U", "uncertain"),
                ai_judgment("SIF-1", "relevant"),
            ],
        }
        result = evaluate([question], documents, k=1, allow_ai_provisional=True)
        self.assertEqual(result["evaluation_status"], "PROVISIONAL")
        self.assertEqual(result["evaluation_policy"], "ai_provisional_candidate_pool")
        self.assertEqual(result["uncertain_candidate_pairs"], 1)
        self.assertEqual(result["hit_rate_at_1"], 0.0)
        self.assertGreaterEqual(result["optimistic_hit_rate_at_1"], result["hit_rate_at_1"])
        self.assertEqual(result["labeled_questions"], 1)

    def test_rejects_missing_provenance(self):
        question = {
            "id": "q001",
            "question": "forklift",
            "status": "ai_provisional",
            "judgments": [ai_judgment("SIF-1", "relevant", evidence_ref="")],
        }
        with self.assertRaisesRegex(ValueError, "missing evidence_ref"):
            evaluate([question], DOCUMENTS, k=1, allow_ai_provisional=True)

    def test_rejects_mixed_label_sets(self):
        questions = [
            {
                "id": "q001",
                "question": "forklift",
                "status": "ai_provisional",
                "judgments": [ai_judgment("SIF-1", "relevant")],
            },
            {
                "id": "q002",
                "question": "fall",
                "status": "human_gold",
                "reviewer": "reviewer_A",
                "expected_case_ids": ["SIF-1"],
            },
        ]
        with self.assertRaisesRegex(ValueError, "every question to be marked ai_provisional"):
            evaluate(questions, DOCUMENTS, k=1, allow_ai_provisional=True)


if __name__ == "__main__":
    unittest.main()

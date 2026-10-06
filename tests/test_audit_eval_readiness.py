import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.sif_rag.audit_eval_readiness import audit_files, audit_questions, load_questions


class EvaluationReadinessTests(unittest.TestCase):
    def write_questions(self, directory, rows):
        path = Path(directory) / "questions.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def write_reviews(self, directory, rows, fields=None):
        path = Path(directory) / "reviews.csv"
        fields = fields or [
            "question_id", "case_id", "human_relevance_label", "human_rationale", "reviewer", "source_url"
        ]
        fields = list(dict.fromkeys([*fields, *(key for row in rows for key in row)]))
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def gold_question(self):
        return {
            "id": "q001", "question": "private query text", "status": "human_gold",
            "expected_case_ids": ["SIF-1"], "reviewer": "reviewer_A",
        }

    def human_review(self, label="relevant", reviewer="reviewer_A"):
        return {
            "question_id": "q001", "case_id": "SIF-1", "human_relevance_label": label,
            "human_rationale": "Evidence supports the query intent.", "reviewer": reviewer,
            "source_url": "https://www.data.go.kr/case/1",
        }

    def test_unlabeled_question_set_is_hold_without_echoing_content(self):
        with tempfile.TemporaryDirectory() as directory:
            questions = self.write_questions(directory, [{
                "id": "q001", "question": "private query text", "status": "needs_label",
                "expected_case_ids": [],
            }])
            report = audit_files(questions)
        serialized = json.dumps(report)
        self.assertEqual(report["status"], "HOLD")
        self.assertEqual(report["question_set"]["gold_ready"], 0)
        self.assertNotIn("private query text", serialized)
        self.assertEqual(len(report["source_files"]["questions"]["sha256"]), 64)

    def test_complete_human_reviewed_inputs_pass_and_count_uncertain(self):
        with tempfile.TemporaryDirectory() as directory:
            questions = self.write_questions(directory, [self.gold_question()])
            second = self.human_review("uncertain")
            second["case_id"] = "SIF-2"
            review = self.write_reviews(directory, [self.human_review(), second])
            report = audit_files(questions, review)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["candidate_review"]["uncertain_count"], 1)

    def test_nonofficial_source_url_blocks_candidate_review(self):
        row = self.human_review()
        row["source_url"] = "https://data.go.kr.attacker.test/case"
        with tempfile.TemporaryDirectory() as directory:
            questions = self.write_questions(directory, [self.gold_question()])
            review = self.write_reviews(directory, [row])
            report = audit_files(questions, review)
        self.assertEqual(report["status"], "HOLD")
        self.assertIn("missing_or_nonofficial_source_url", report["candidate_review"]["issue_counts"])

    def test_assistant_second_pass_is_not_human_gold(self):
        with tempfile.TemporaryDirectory() as directory:
            questions = self.write_questions(directory, [self.gold_question()])
            review = self.write_reviews(directory, [self.human_review(reviewer="assistant_second_pass")])
            report = audit_files(questions, review)
        self.assertEqual(report["status"], "HOLD")
        self.assertEqual(report["candidate_review"]["assistant_or_automated_rows"], 1)

    def test_generic_relevance_label_is_not_accepted_as_human_label(self):
        row = self.human_review()
        row["relevance_label"] = row.pop("human_relevance_label")
        with tempfile.TemporaryDirectory() as directory:
            questions = self.write_questions(directory, [self.gold_question()])
            review = self.write_reviews(directory, [row])
            report = audit_files(questions, review)
        self.assertEqual(report["status"], "HOLD")
        self.assertIn("missing_or_invalid_human_label", report["candidate_review"]["issue_counts"])

    def test_duplicate_question_id_is_not_counted_ready(self):
        row = self.gold_question()
        self.assertEqual(audit_questions([row, row])["gold_ready"], 1)

    def test_invalid_json_reports_line_number_without_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            path.write_text('{"id":"q1"}\nnot-json secret text\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 2"):
                load_questions(path)


if __name__ == "__main__":
    unittest.main()

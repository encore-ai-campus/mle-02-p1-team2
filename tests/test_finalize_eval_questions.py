import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.sif_rag.audit_eval_readiness import audit_files
from src.sif_rag.finalize_eval_questions import finalize_question_labels


class FinalizeEvaluationQuestionsTests(unittest.TestCase):
    columns = ["question_id", "case_id", "human_relevance_label", "human_rationale", "reviewer", "source_url"]

    def write_inputs(self, directory, labels=None, reviewers=None):
        root = Path(directory)
        questions = root / "questions.jsonl"
        questions.write_text(
            json.dumps({"id": "q1", "question": "work context", "status": "needs_label", "expected_case_ids": []}) + "\n",
            encoding="utf-8",
        )
        labels = labels or [("SIF-1", "relevant"), ("SIF-2", "not_relevant"), ("SIF-3", "uncertain")]
        reviewers = reviewers or ["reviewer_A"] * len(labels)
        review = root / "review.csv"
        with review.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.columns)
            writer.writeheader()
            for (case_id, label), reviewer in zip(labels, reviewers):
                writer.writerow({
                    "question_id": "q1", "case_id": case_id, "human_relevance_label": label,
                    "human_rationale": "Reviewed against source evidence.", "reviewer": reviewer,
                    "source_url": f"https://www.data.go.kr/case/{case_id}",
                })
        return questions, review

    def test_creates_auditable_gold_questions_and_preserves_review_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            questions, review = self.write_inputs(directory)
            before = review.read_bytes()
            output = Path(directory) / "gold.jsonl"
            self.assertEqual(finalize_question_labels(questions, review, output), 1)
            result = json.loads(output.read_text(encoding="utf-8").strip())
            audit = audit_files(output, review)
            after = review.read_bytes()
        self.assertEqual(result["status"], "human_gold")
        self.assertEqual(result["expected_case_ids"], ["SIF-1"])
        self.assertEqual(result["reviewer"], "reviewer_A")
        self.assertEqual(after, before)
        self.assertEqual(audit["status"], "PASS")

    def test_rejects_assistant_attributed_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            questions, review = self.write_inputs(directory, reviewers=["assistant_review"] * 3)
            with self.assertRaisesRegex(ValueError, "provenance"):
                finalize_question_labels(questions, review, Path(directory) / "gold.jsonl")

    def test_rejects_conflicting_reviewers_for_one_question(self):
        with tempfile.TemporaryDirectory() as directory:
            questions, review = self.write_inputs(directory, reviewers=["reviewer_A", "reviewer_B", "reviewer_A"])
            with self.assertRaisesRegex(ValueError, "one consistent human reviewer"):
                finalize_question_labels(questions, review, Path(directory) / "gold.jsonl")

    def test_rejects_question_without_relevant_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            labels = [("SIF-1", "not_relevant"), ("SIF-2", "uncertain")]
            questions, review = self.write_inputs(directory, labels)
            with self.assertRaisesRegex(ValueError, "at least one relevant"):
                finalize_question_labels(questions, review, Path(directory) / "gold.jsonl")

    def test_refuses_to_overwrite_an_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            questions, review = self.write_inputs(directory)
            output = Path(directory) / "gold.jsonl"
            output.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "Output already exists"):
                finalize_question_labels(questions, review, output)
            self.assertEqual(output.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()

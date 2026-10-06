import csv
import tempfile
import unittest
from pathlib import Path

from src.sif_rag.prepare_eval_review_template import prepare_review_template


class PrepareReviewTemplateTests(unittest.TestCase):
    def write_csv(self, path, columns, rows):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    def test_clears_machine_and_prior_labels_but_keeps_candidate_evidence(self):
        columns = ["question_id", "question", "case_id", "incident_overview", "source_url", "relevance_label", "review_notes", "reviewer", "metric_eligible"]
        row = {
            "question_id": "q1", "question": "query", "case_id": "SIF-1",
            "incident_overview": "evidence", "source_url": "https://www.data.go.kr/case/1",
            "relevance_label": "relevant", "review_notes": "auto note", "reviewer": "assistant_second_pass", "metric_eligible": "true",
        }
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "candidates.csv", Path(directory) / "template.csv"
            self.write_csv(source, columns, [row])
            self.assertEqual(prepare_review_template(source, output), 1)
            with output.open(encoding="utf-8-sig", newline="") as stream:
                result = next(csv.DictReader(stream))
        self.assertEqual(result["incident_overview"], "evidence")
        self.assertEqual(result["relevance_label"], "")
        self.assertEqual(result["review_notes"], "")
        self.assertEqual(result["reviewer"], "")
        self.assertEqual(result["metric_eligible"], "")
        self.assertEqual(result["human_relevance_label"], "")
        self.assertEqual(result["human_rationale"], "")

    def test_rejects_missing_identifiers_or_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "bad.csv", Path(directory) / "template.csv"
            self.write_csv(source, ["question_id", "case_id"], [{"question_id": "q1", "case_id": "SIF-1"}])
            with self.assertRaisesRegex(ValueError, "source_url"):
                prepare_review_template(source, output)

    def test_rejects_same_input_and_output_path(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "candidates.csv"
            self.write_csv(source, ["question_id", "case_id", "source_url"], [])
            with self.assertRaisesRegex(ValueError, "must be different"):
                prepare_review_template(source, source)


if __name__ == "__main__":
    unittest.main()

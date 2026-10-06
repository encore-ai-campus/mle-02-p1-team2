"""Convert retrieval candidates into a blank, provenance-aware human-review CSV."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

REQUIRED_INPUT_COLUMNS = {"question_id", "case_id", "source_url"}
REVIEW_COLUMNS = ("human_relevance_label", "human_rationale", "reviewer")
LABEL_COLUMNS_TO_CLEAR = (*REVIEW_COLUMNS, "relevance_label", "review_notes", "metric_eligible")


def _is_annotation_column(name: str) -> bool:
    normalized = name.casefold()
    return (
        normalized in LABEL_COLUMNS_TO_CLEAR
        or "label" in normalized
        or "rationale" in normalized
        or "review" in normalized
        or normalized.startswith(("assistant_", "ai_", "model_"))
    )


def prepare_review_template(source_path: Path, output_path: Path) -> int:
    if source_path.resolve() == output_path.resolve():
        raise ValueError("Input and output paths must be different.")

    with source_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)):
            raise ValueError("Candidate CSV contains duplicate column names.")
        missing = sorted(REQUIRED_INPUT_COLUMNS - set(columns))
        if missing:
            raise ValueError("Candidate CSV is missing required columns: " + ", ".join(missing))
        rows = list(reader)

    output_columns = list(columns)
    for column in REVIEW_COLUMNS:
        if column not in output_columns:
            output_columns.append(column)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=output_columns, extrasaction="ignore")
        writer.writeheader()
        annotation_columns = {column for column in output_columns if _is_annotation_column(column)}
        for row in rows:
            normalized = {column: row.get(column, "") or "" for column in output_columns}
            for column in annotation_columns:
                normalized[column] = ""
            writer.writerow(normalized)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a blank human-review template from retrieval candidates; no labels are assigned."
    )
    parser.add_argument("--input", type=Path, required=True, help="Candidate-review CSV")
    parser.add_argument("--output", type=Path, required=True, help="New human-review template CSV")
    args = parser.parse_args()
    try:
        count = prepare_review_template(args.input, args.output)
    except (OSError, csv.Error, ValueError) as exc:
        parser.error(str(exc))
    print(f"candidates={count} output={args.output}")
    print("Human label, rationale, and reviewer fields were cleared for independent review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

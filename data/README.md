# Data files

Keep source data, generated corpora, embeddings, and evaluation outputs separate from code. Do not commit source or derived data until the provider's terms and publication permission are confirmed.

```text
data/
├── raw/         # Original source files; ignored by Git
├── interim/     # Re-creatable intermediate outputs; ignored by Git
├── processed/   # Local processing outputs; only permission and audit notes are tracked
└── evaluation/
    ├── questions/  # Versioned question set, when approved
    ├── labels/     # Reviewed relevance judgments, when approved
    └── reports/    # Local run metrics and error analysis; ignored by Git
```

## Rules

- Keep original files unchanged and record their source and version.
- Store evaluation questions, reviewed labels, and generated reports separately under `data/evaluation/questions/`, `labels/`, and `reports/`.
- Do not publish source text, collected JSONL, embeddings, or vector databases before confirming the applicable terms.
- Keep credentials and sensitive values in the local `.env` file.
- Add a data artifact to Git only after its publication scope has been reviewed and approved.

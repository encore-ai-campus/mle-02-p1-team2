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

## Retrieval evaluation protocol

- Put question JSONL under `data/evaluation/questions/`; every item needs a stable `id`, `question`, and optional `industry_filter`.
- Generate `data/evaluation/labels/rag_query_ablation_pilot_10q.csv` with `python -m src.sif_rag.prepare_query_ablation`. It contains the union of each question's raw, focused, and glossary BM25 top-k candidates; no relevance labels are generated automatically.
- Review every candidate row. Use `relevant`, `not_relevant`, or `uncertain` in `relevance_label`; set `review_status` to `human_reviewed`; record reviewer identity, the evidence reference, and a short rationale in `review_notes`. Do not promote assistant-generated judgments to human-reviewed labels.
- Compare only a fully reviewed candidate pool with `python -m src.sif_rag.evaluate --review-pool data/evaluation/labels/rag_query_ablation_pilot_10q.csv -k 3`. The primary report excludes uncertain labels; the sensitivity report counts them as relevant. Metrics are capped at the reviewed pool depth. `pooled_recall` means recall against relevant cases in this judged union, not recall over the full archive.
- The interactive CLI supports `python -m src.sif_rag.rag_cli "..." --retriever bm25` and `--retriever vector`; vector retrieval requires an initialized pgvector corpus and supports only `text-embedding-3-small` (1536 dimensions) with the current schema.
- Keep evaluation reports in `data/evaluation/reports/`; these outputs remain local and ignored by Git.

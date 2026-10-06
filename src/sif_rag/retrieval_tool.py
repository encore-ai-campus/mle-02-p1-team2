"""Structured, citation-checked interface for SIF case retrieval."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from .search import bm25

TOOL_NAME = "search_sif_cases"
TOOL_DESCRIPTION = (
    "Search the locally available SIF accident-case corpus and return ranked case evidence "
    "with source identifiers and URLs. BM25 scores are ranking signals, not probabilities."
)


def tool_schema() -> dict[str, Any]:
    """Return a provider-neutral JSON schema for Agent/tool registration."""
    return {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "description": "Work context or accident risk query"},
                "industry": {"type": ["string", "null"], "description": "Optional user-specified industry filter (substring match)"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    }


def _text(fields: dict[str, Any], key: str) -> str | None:
    value = fields.get(key)
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _valid_source_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").casefold()
    official_host = host == "data.go.kr" or host.endswith(".data.go.kr")
    return parsed.scheme in {"http", "https"} and official_host


def search_sif_cases(
    query: str,
    corpus: list[dict[str, Any]],
    *,
    industry: str | None = None,
    top_k: int = 3,
) -> dict[str, Any]:
    """Return citable cases as stable JSON; malformed citations are excluded.

    URL validation is structural and does not fetch external pages.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 5:
        raise ValueError("top_k must be an integer from 1 to 5")
    if industry is not None and (not isinstance(industry, str) or not industry.strip()):
        raise ValueError("industry must be omitted or a non-empty string")

    ranked = bm25(query.strip(), corpus, k=top_k, industry=industry.strip() if industry else None)
    results: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    for score, document in ranked:
        case_id = str(document.get("case_id") or "").strip()
        source_url = document.get("source_url")
        if not case_id:
            warnings.append("Excluded a candidate with no case ID during citation validation.")
            continue
        if case_id in seen_ids:
            warnings.append(f"Excluded duplicate candidate case ID {case_id}.")
            continue
        if not _valid_source_url(source_url):
            warnings.append(f"Excluded case {case_id}: missing or invalid official data.go.kr HTTP(S) source URL.")
            continue
        seen_ids.add(case_id)
        raw_fields = document.get("fields")
        fields = raw_fields if isinstance(raw_fields, dict) else {}
        industry_values = [
            value for key in ("sifLclsfNm", "sifMclsfNm", "sifSclsfNm")
            if (value := _text(fields, key))
        ]
        results.append(
            {
                "rank": len(results) + 1,
                "case_id": case_id,
                "score": round(float(score), 6),
                "score_type": "bm25",
                "evidence": {
                    "industry": " > ".join(industry_values) or None,
                    "incident_overview": _text(fields, "disasterOverview"),
                    "object": _text(fields, "orgtNm"),
                    "high_risk_work": _text(fields, "situation"),
                    "risk_factor": _text(fields, "disasterFactor"),
                    "control_measure": _text(fields, "dcrsCntrplnCn"),
                },
                "citation": {
                    "source_url": source_url.strip(),
                    "validation": {
                        "http_scheme": True,
                        "official_data_go_kr_host": True,
                        "case_identity": "not_checked",
                    },
                },
            }
        )

    return {
        "tool": TOOL_NAME,
        "status": "ok" if results else "no_citable_results",
        "query": query.strip(),
        "filters": {"industry": industry.strip() if industry else None},
        "retrieval": {"method": "bm25", "top_k": top_k, "score_is_probability": False},
        "results": results,
        "warnings": warnings,
        "corpus_note": "Results cover only the collected SIF API sample, not the full archive.",
    }

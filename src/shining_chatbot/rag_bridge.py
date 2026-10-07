"""Run the existing SANUP-P RAG pipeline in its own Python environment.

The Streamlit app sends one JSON request on stdin. This process returns one JSON
result on stdout and never prints credentials or raw exception messages.
"""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import stat
import sys
import tempfile
from uuid import uuid4
from pathlib import Path


SOURCE_TYPES = {
    "all": None,
    "sif": "sif",
    "moel_report": "moel_report",
    "kosha_guide": "kosha_guide",
}
SEARCH_MODES = {"semantic", "hybrid_rrf", "lexical"}


def _effective_search_mode(mode: str, generate: object) -> tuple[str, bool]:
    """Enforce the UI's external-service consent at the process boundary."""
    if mode not in SEARCH_MODES or not isinstance(generate, bool):
        raise ValueError("invalid_filter")
    return (mode if generate else "lexical"), generate


def _writable_index_copy(root: Path) -> Path:
    """Make a reusable local Chroma copy when the source index is read-only."""
    corpus = root / "data" / "personal" / "corpus"
    database = root / "chroma_db" / "personal"
    source_files = (corpus / "chunks.jsonl", corpus / "index_meta.json", corpus / "index_meta_semantic.json")
    signature = [
        (str(path.resolve()), path.stat().st_size, path.stat().st_mtime_ns)
        for path in (*source_files, database / "chroma.sqlite3")
    ]
    key = hashlib.sha256(json.dumps(signature, ensure_ascii=True).encode("utf-8")).hexdigest()[:20]
    cache_parent = Path(os.getenv("SANUP_P_CACHE_DIR") or tempfile.gettempdir()) / "shining-chatbot-sanup-index"
    cache = cache_parent / key
    if (cache / "chroma_db" / "personal" / "chroma.sqlite3").is_file():
        return cache

    cache_parent.mkdir(parents=True, exist_ok=True)
    staging = cache_parent / f".{key}-{uuid4().hex}"
    try:
        (staging / "data" / "personal" / "corpus").mkdir(parents=True)
        for source in source_files:
            shutil.copy2(source, staging / "data" / "personal" / "corpus" / source.name)
        shutil.copytree(database, staging / "chroma_db" / "personal", copy_function=shutil.copy2)
        copied_db = staging / "chroma_db" / "personal" / "chroma.sqlite3"
        os.chmod(copied_db, stat.S_IREAD | stat.S_IWRITE)
        try:
            os.replace(staging, cache)
        except OSError:
            if not (cache / "chroma_db" / "personal" / "chroma.sqlite3").is_file():
                raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return cache


def run(root: Path, request: dict) -> dict:
    sys.path.insert(0, str(root))
    from dotenv import dotenv_values
    from langchain_openai import ChatOpenAI
    from src.rag_chain import build_rag_chain
    from src.retriever import PersonalRetriever

    question = str(request.get("question") or "").strip()
    if not question or len(question) > 2000:
        raise ValueError("invalid_question")
    mode = str(request.get("mode") or "semantic")
    mode, generate = _effective_search_mode(mode, request.get("generate", False))
    source = str(request.get("source") or "all")
    if source not in SOURCE_TYPES:
        raise ValueError("invalid_filter")

    config = dotenv_values(root / ".env")
    api_key = (os.getenv("OPENAI_API_KEY") or config.get("OPENAI_API_KEY") or "").strip()
    if mode != "lexical" and not api_key:
        raise ValueError("semantic_key_missing")
    llm = None
    if api_key and generate:
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL") or config.get("OPENAI_MODEL") or "gpt-6-luna",
            api_key=api_key,
            timeout=60,
            max_retries=0,
            max_completion_tokens=1200,
            reasoning_effort="low",
        )

    try:
        retriever = PersonalRetriever(root, mode=mode)
    except Exception as exc:
        if "readonly database" not in str(exc).lower() and "read-only database" not in str(exc).lower():
            raise
        retriever = PersonalRetriever(_writable_index_copy(root), mode=mode)
    if mode != "lexical" and api_key:
        from openai import OpenAI
        retriever._openai = OpenAI(api_key=api_key, timeout=60, max_retries=2)
    tbm = bool(request.get("tbm"))
    retrieve = retriever.retrieve_tbm if tbm else retriever.retrieve
    retrieved: list[dict] = []

    def tracked_retrieve(*args, **kwargs):
        hits = retrieve(*args, **kwargs)
        retrieved[:] = hits
        return hits

    chain = build_rag_chain(tracked_retrieve, llm, min_similarity=0.12 if mode == "lexical" else 0.38)
    chain_input = {
            "question": question,
            "source_type": None if tbm else SOURCE_TYPES[source],
            "required_source_types": ["sif", "kosha_guide"] if tbm else None,
            "industry_major": str(request.get("industry_major") or "").strip() or None,
            "equipment": str(request.get("equipment") or "").strip() or None,
            "work_context": str(request.get("work_context") or "").strip()[:500],
            "chat_history": request.get("history") or [],
        }
    result = chain.invoke(chain_input)
    if llm is not None and result.get("status") in {"unsupported_citation", "malformed_quantity", "empty_response"}:
        result = chain.invoke(chain_input)
    if api_key and not generate and result.get("status") == "llm_key_missing":
        result["status"] = "generation_disabled"
    answer = result.get("answer") or ""
    sources = []
    for position, hit in enumerate(result.get("sources") or []):
        metadata = hit.get("metadata") or {}
        citation_number = next(
            (index for index, original in enumerate(retrieved, start=1) if original is hit),
            position + 1,
        )
        sources.append(
            {
                "number": citation_number,
                "title": str(metadata.get("title") or hit.get("doc_id") or "제목 없음"),
                "organization": str(metadata.get("organization") or ""),
                "url": str(metadata.get("source_url") or ""),
                "page": metadata.get("page"),
                "doc_id": str(hit.get("doc_id") or ""),
                "source_type": str(metadata.get("source_type") or ""),
                "ocr_review_required": bool(metadata.get("ocr_review_required")),
            }
        )
    return {"status": result.get("status"), "answer": answer, "sources": sources}


def main() -> None:
    try:
        root = Path(sys.argv[1]).resolve()
        request = json.load(sys.stdin)
        output = run(root, request)
    except Exception as exc:
        kind = type(exc).__name__
        detail = str(exc).lower()
        if "readonly database" in detail or "read-only database" in detail:
            code = "index_readonly"
        elif kind == "ValueError" and "semantic_key_missing" in detail:
            code = "semantic_key_missing"
        elif kind == "RuntimeError" and "index" in detail:
            code = "index_invalid"
        else:
            code = kind
        output = {"status": "error", "code": code, "answer": "", "sources": []}
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()

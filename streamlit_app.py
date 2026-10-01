"""Minimal Streamlit UI for the SIF BM25 + grounded generation prototype."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.sif_rag.query_expansion import DEFAULT_GLOSSARY, GlossaryExpander
from src.sif_rag.rag_cli import format_answer, generate_grounded_answer
from src.sif_rag.search import bm25, load_corpus
from src.sif_rag.vector_store import vector_search


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CORPUS = PROJECT_ROOT / "data" / "processed" / "sif_rag_documents.jsonl"


@st.cache_data(show_spinner=False)
def get_corpus(path: str, modified_at: float) -> list[dict]:
    """Load the local JSONL corpus once and refresh if its mtime changes."""
    del modified_at
    return load_corpus(Path(path))


@st.cache_data(show_spinner=False)
def get_industries(path: str, modified_at: float) -> list[str]:
    del modified_at
    corpus = load_corpus(Path(path))
    values = {
        str(document.get("fields", {}).get("sifLclsfNm", "")).strip()
        for document in corpus
    }
    return sorted(value for value in values if value)


def main() -> None:
    st.set_page_config(page_title="산업재해 유사사례 RAG", page_icon="🦺", layout="wide")
    st.title("산업재해 유사사례 RAG")
    st.caption(
        "SIF API에서 수집한 키워드 표본으로 유사 사례를 검색합니다. 전체 아카이브가 아니며, "
        "결과는 현장 안전관리자 검토를 위한 참고자료입니다."
    )

    corpus_path = DEFAULT_CORPUS
    if not corpus_path.exists():
        st.error(f"사례 문서 파일을 찾을 수 없습니다: {corpus_path}")
        st.stop()

    modified_at = corpus_path.stat().st_mtime
    corpus = get_corpus(str(corpus_path), modified_at)
    industries = get_industries(str(corpus_path), modified_at)

    with st.form("rag_query_form"):
        question = st.text_area(
            "작업 상황 또는 안전 질문",
            placeholder="예: 물류창고에서 지게차로 자재를 옮길 때 보행자 충돌을 어떻게 예방할 수 있나요?",
            height=100,
        )
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            industry = st.selectbox("업종 대분류 필터", ["전체 업종", *industries])
        with col2:
            result_count = st.slider("사례 수", min_value=1, max_value=5, value=3)
        with col3:
            retrieval_mode = st.selectbox("검색 방식", ["키워드 (BM25)", "의미 검색 (pgvector)"])
        answer_mode = st.selectbox(
            "응답 방식",
            ["근거 기반 답변 생성", "검색 결과만 표시"],
            help="답변 생성은 제출할 때 OpenAI API를 호출합니다.",
        )
        expand_query = st.checkbox("산업안전 용어사전으로 검색어 확장", value=False)
        submitted = st.form_submit_button("사례 검색", type="primary", use_container_width=True)

    if not submitted:
        st.info("작업 상황을 입력하고 사례 검색을 누르세요.")
        return
    if not question.strip():
        st.warning("작업 상황이나 질문을 입력해 주세요.")
        return

    expanded_query = question.strip()
    expansion: dict | None = None
    if expand_query:
        if not DEFAULT_GLOSSARY.exists():
            st.error(f"용어사전 파일을 찾을 수 없습니다: {DEFAULT_GLOSSARY}")
            return
        expansion = GlossaryExpander.from_csv(DEFAULT_GLOSSARY).expand(expanded_query)
        expanded_query = str(expansion["expanded_query"])

    selected_industry = None if industry == "전체 업종" else industry
    if retrieval_mode == "의미 검색 (pgvector)":
        with st.spinner("pgvector에서 유사 사례를 찾고 있습니다…"):
            try:
                results = vector_search(
                    expanded_query,
                    k=result_count,
                    industry=selected_industry,
                )
            except Exception as exc:
                st.error(f"의미 검색에 실패했습니다: {exc}")
                return
    else:
        results = bm25(expanded_query, corpus, k=result_count, industry=selected_industry)
    if expansion and expansion.get("added_terms"):
        st.caption(f"확장 검색어: {expanded_query}")

    if not results:
        st.warning(
            "현재 수집된 사례에서 근거를 찾지 못했습니다. 질문 표현을 바꾸거나 업종 필터를 해제해 보세요. "
            "이 코퍼스는 키워드 수집 표본입니다."
        )
        return

    if answer_mode == "근거 기반 답변 생성":
        with st.spinner("검색된 사례를 바탕으로 답변을 작성하고 있습니다…"):
            try:
                answer = generate_grounded_answer(question.strip(), results, model=None)
            except Exception as exc:
                st.error(f"답변 생성에 실패했습니다: {exc}")
                st.info("‘검색 결과만 표시’를 선택하면 API 호출 없이 원문 사례를 볼 수 있습니다.")
                return
    else:
        answer = format_answer(
            question.strip(),
            results,
            expanded_query=expanded_query if expansion else None,
            added_terms=list(expansion["added_terms"]) if expansion else None,
            score_label="코사인 유사도" if retrieval_mode == "의미 검색 (pgvector)" else "BM25",
        )

    st.markdown(answer)


if __name__ == "__main__":
    main()

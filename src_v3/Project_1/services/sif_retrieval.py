"""SIF-only query preparation and hybrid candidate ranking.

There is no subject allowlist. Request boilerplate is removed, while unfamiliar
industries, materials, equipment and accident expressions remain searchable.
KOSHA query analysis and retrieval deliberately do not use this module.
"""
import re
import unicodedata

from langchain_core.documents import Document


REQUEST_WORDS = frozenset("""
그럼 그러면 그중 이것 그것 관련 대한 대해 대해서 어떤 무엇 어떻게 알려줘
알려주세요 알려 주세 주세요 해줘 해주세요 설명 설명해줘 설명해주세요 찾아줘
찾아주세요 보여줘 보여주세요 정리 정리해줘 작업 중 때 공장 현장 공정 업종 분야
사고 사례 사고사례 산업재해 재해 유사 실제 발생 발생한 발생하는 발생했던
경위 원인 재해유발요인 위험요인 위험 안전 예방 대책 예방대책 예방방법 방법
점검 확인 확인사항 점검사항 사항 조치 안전조치 작업방법 작업전 전에 후에
필요 주의 궁금 궁금해 궁금합니다 합니다 있는데 있어 있는 대해 알려 줄 알려줄
저 저희 우리 오늘 동료 함께 오전 오후 대해서 예시 내용 구체적 구체적인
좀 및 등 또는 혹은 와 과 의 내 알려줄래 알려주실 수 있을까요 있나요
""".split())
PARTICLE_SUFFIXES = ("으로부터", "에서는", "에서도", "에서의", "으로는", "으로", "에서",
                     "에게", "부터", "까지", "처럼", "보다", "에는", "와", "과",
                     "을", "를", "은", "는", "이", "가", "에", "의", "로", "도")


def search_terms(text: str) -> tuple[str, ...]:
    """Keep all distinct subject tokens, including those after the sixth token.

    This conservative particle stripping is not a Korean morphological parser.
    Query intent is still preserved in the original question used by the reranker.
    """
    found = []
    for token in re.findall(r"[가-힣a-zA-Z0-9]+", unicodedata.normalize("NFKC", text).casefold()):
        if token in REQUEST_WORDS:
            continue
        for suffix in PARTICLE_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 2:
                token = token[:-len(suffix)]
                break
        if len(token) >= 2 and token not in REQUEST_WORDS and token not in found:
            found.append(token)
    return tuple(found)


def embedding_query(text: str) -> str:
    """Do not append generic accident vocabulary that dilutes rare subjects."""
    return " ".join(search_terms(text)) or text.strip()


# Only accident facts and semantic classification fields participate. Provenance
# fields (source_file, sheet, row_number, group) must never satisfy a query term.
# Literal strpos avoids interpreting %, _ or user text as SQL LIKE patterns.
# Corpus document frequency downweights broad terms such as '제조'; this is an
# IDF-weighted lexical score, not BM25. No corpus or subject lists are downloaded.
KEYWORD_SQL = """
WITH searchable AS MATERIALIZED (
    SELECT source_id, content, metadata, embedding,
           lower(concat_ws(' ', split_part(content, '위험성 감소대책(예시):', 1),
               metadata->>'기인물', metadata->>'재해유발요인', metadata->>'재해종류',
               metadata->>'대분류', metadata->>'중분류', metadata->>'소분류',
               metadata->>'작업중분류', metadata->>'작업소분류')) AS search_text
    FROM rag_day1_documents
    WHERE kind='sif_case' AND embedding_model=%s AND vector_dims(embedding)=%s
), matches AS MATERIALIZED (
    SELECT d.source_id, t.term FROM searchable d
    CROSS JOIN unnest(%s::text[]) AS t(term)
    WHERE strpos(d.search_text, t.term) > 0
), frequencies AS (
    SELECT term, count(*) AS df FROM matches GROUP BY term
), scores AS (
    SELECT m.source_id,
           sum(ln(1.0 + (SELECT count(*) FROM searchable) / (1.0 + f.df))) AS lexical_score,
           array_agg(m.term ORDER BY m.term) AS matched_terms
    FROM matches m JOIN frequencies f USING (term) GROUP BY m.source_id
)
SELECT d.source_id, d.content, d.metadata, d.embedding <=> %s AS distance,
       s.lexical_score, s.matched_terms
FROM searchable d JOIN scores s USING (source_id)
ORDER BY s.lexical_score DESC, distance, d.source_id LIMIT %s
"""


def fuse_candidates(keyword_documents, vector_documents) -> list[Document]:
    """Deduplicate the COMPLETE bounded union before LLM reranking.

    Reciprocal rank fusion supplies ordering and a deterministic fallback; it
    cannot evict candidates from either channel. Each channel is already capped
    by the caller, so at most twice CANDIDATE_K documents reach the reranker.
    """
    documents, scores, channels = {}, {}, {}
    for channel, hits in (("keyword", keyword_documents), ("vector", vector_documents)):
        seen = set()
        for rank, doc in enumerate(hits, 1):
            identifier = doc.metadata["source_id"]
            if identifier in seen:
                continue
            seen.add(identifier)
            if identifier not in documents:
                documents[identifier] = doc
                scores[identifier] = 0.0
                channels[identifier] = []
            scores[identifier] += 1.0 / (60 + rank)
            channels[identifier].append(channel)
    ordered = sorted(documents, key=lambda identifier: (
        -scores[identifier], float(documents[identifier].metadata.get("distance", 1)), identifier))
    return [Document(page_content=documents[key].page_content,
                     metadata={**documents[key].metadata, "retrieval_channels": channels[key],
                               "fusion_score": scores[key]}) for key in ordered]

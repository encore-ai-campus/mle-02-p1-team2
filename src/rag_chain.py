"""Source-aware RAG chain for the personal SANUP-P corpus.

The retriever is injected so the existing, evaluated Chroma index can be used
without silently changing its lexical embedding method.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough


UNKNOWN = "제공된 근거 자료에서 답을 확인할 수 없습니다."


def build_rag_chain(
    retrieve: Callable[..., list[dict[str, Any]]],
    llm: Any | None,
    *,
    min_similarity: float = 0.12,
):
    """Build retrieval -> evidence gate -> prompt -> model -> citation check."""

    def search(request: dict[str, Any]) -> dict[str, Any]:
        question = str(request.get("question", "")).strip()
        if not question:
            raise ValueError("질문을 입력하세요.")
        work_context = str(request.get("work_context") or "").strip()[:500]
        history = request.get("chat_history") or []
        if not isinstance(history, list):
            raise ValueError("chat_history must be a list")
        recent = [
            {"role": item.get("role"), "content": str(item.get("content", "")).strip()[:500]}
            for item in history[-4:]
            if isinstance(item, dict) and item.get("role") in {"user", "assistant"}
        ]
        retrieval_question = question
        if work_context:
            retrieval_question += f"\n현재 작업: {work_context}"
        if recent and len(question) < 30:
            last_user = next((item["content"] for item in reversed(recent)
                              if item["role"] == "user"), "")
            if last_user:
                retrieval_question += f"\n앞선 질문: {last_user}"
        kwargs: dict[str, Any] = {"k": 5, "source_type": request.get("source_type")}
        for name in ("industry_major", "equipment"):
            if request.get(name):
                kwargs[name] = str(request[name]).strip()
        hits = retrieve(retrieval_question, **kwargs)
        required_source_types = set(request.get("required_source_types") or [])
        return {"question": question, "work_context": work_context, "history": recent,
                "hits": hits, "required_source_types": required_source_types}

    def insufficient(context: dict[str, Any]) -> bool:
        if not context["hits"]:
            return True
        if (context["hits"][0]["similarity"] < min_similarity
                and not context["hits"][0].get("exact_doc_id_match")):
            return True
        found = {hit.get("metadata", {}).get("source_type") for hit in context["hits"]}
        return not context["required_source_types"].issubset(found)

    def no_evidence(context: dict[str, Any]) -> dict[str, Any]:
        return {"answer": UNKNOWN, "sources": [], "status": "insufficient_evidence"}

    def no_key(context: dict[str, Any]) -> dict[str, Any]:
        return {"answer": None, "sources": context["hits"], "status": "llm_key_missing"}

    search_chain = RunnableLambda(search)
    if llm is None:
        return search_chain | RunnableBranch(
            (insufficient, RunnableLambda(no_evidence)), RunnableLambda(no_key)
        )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "당신은 산업안전 자료를 근거로 답하는 도우미입니다. "
                "제공된 근거 밖의 사실을 추측하지 마세요. "
                "질문에 문서 ID나 사례 ID가 있으면 그 ID가 일치하는 자료만 근거로 답하고, "
                "해당 ID 자료에서 답을 확인할 수 없으면 다른 유사 사례로 대신하지 말고 모른다고 답하세요. "
                "KOSHA GUIDE가 법령 조항을 인용해도 현행 법령 원문을 확인하지 않았다면 현재 법적 의무로 단정하지 말고, "
                "GUIDE의 인용 내용이라고 밝히며 현행 조문 확인이 필요하다고 덧붙이세요. "
                f"답을 확인할 수 없으면 정확히 '{UNKNOWN}'라고 답하세요. "
                "답변의 각 핵심 주장에 [1] 같은 근거 번호를 붙이세요. "
                "근거에 직접 적혀 있지 않은 일반적인 안전 수칙은 추가하지 마세요. "
                "TBM 체크리스트 요청에는 '사고사례에서 확인할 점'과 '안전지침에서 확인할 점'을 나누고, "
                "각 제목 아래 근거가 있는 확인 항목만 최대 5개, '- [ ] 항목.[번호]' 형식으로 씁니다. "
                "TBM 체크리스트를 요청하지 않았다면 이 제목을 쓰지 말고, 비어 있는 제목이나 항목을 출력하지 마세요. "
                "SIF 사고사례 항목은 SIF 출처를, 안전지침 항목은 KOSHA GUIDE 출처를 각각 인용하세요. "
                "서로 다른 자료의 내용을 공통 위험이라고 뭉뚱그리지 마세요. "
                "목록의 각 항목 끝에는 해당 근거 번호를 반드시 붙이고, "
                "근거가 없는 항목은 생략하세요. "
                "답을 찾았다면 '- 확인한 내용.[1]' 형식의 목록으로만 답하세요. "
                "목록 밖에는 새로운 사실 주장을 쓰지 마세요. "
                "이전 대화와 작업 정보는 질문 해석에만 사용하고 사실 근거로 인용하지 마세요. "
                "이 답변은 현장 위험성평가나 공식 안전지침을 대체하지 않습니다.",
            ),
            ("human", "현재 작업: {work_context}\n이전 대화: {history}\n"
             "질문: {question}\n\n검색된 근거:\n{evidence}"),
        ]
    )

    def prompt_input(context: dict[str, Any]) -> dict[str, str]:
        labels = {"sif": "SIF 사고사례", "moel_report": "사고조사보고서", "kosha_guide": "KOSHA 안전지침"}
        evidence = "\n\n".join(
            f"[{i}] [{labels.get(hit['metadata'].get('source_type', '자료'), hit['metadata'].get('source_type', '자료'))}] "
            f"{hit['metadata']['title']} | {hit['metadata']['source_url']} | "
            f"{hit['metadata']['page']}쪽 | 문서 ID {hit['doc_id']}"
            f"{' | OCR 자동 인식, 원문 대조 필요' if hit['metadata'].get('ocr_review_required') else ''}\n"
            f"{hit['text']}"
            for i, hit in enumerate(context["hits"], start=1)
        )
        history = "\n".join(f"{item['role']}: {item['content']}" for item in context["history"])
        return {"question": context["question"], "work_context": context["work_context"],
                "history": history, "evidence": evidence}

    answer_chain = RunnableLambda(prompt_input) | prompt | llm | StrOutputParser()

    def package(context: dict[str, Any]) -> dict[str, Any]:
        answer = context["answer"].strip()
        hits = context["hits"]
        if not answer:
            return {"answer": None, "sources": hits, "status": "empty_response"}
        abstention = re.sub(r"^\s*[-*]\s+", "", answer).strip()
        if abstention == UNKNOWN:
            return {"answer": answer, "sources": [], "status": "insufficient_evidence"}
        cited = {int(number) for number in re.findall(r"\[(\d+)\]", answer)}
        if not cited or not cited.issubset(set(range(1, len(hits) + 1))):
            return {"answer": None, "sources": hits, "status": "unsupported_citation"}
        guide_citations = sorted(
            index for index in cited
            if hits[index - 1].get("metadata", {}).get("source_type") == "kosha_guide"
        )
        if guide_citations and "현행 법령과 일치한다고 단정하지 않습니다" not in answer:
            answer += (
                "\n- 참고: 이 답변은 인용한 KOSHA GUIDE의 기술 안내를 정리한 것이며, "
                f"현행 법령과 일치한다고 단정하지 않습니다.[{guide_citations[0]}]"
            )
        cited_sources = {hits[i - 1].get("metadata", {}).get("source_type") for i in cited}
        if not context["required_source_types"].issubset(cited_sources):
            return {"answer": None, "sources": hits, "status": "unsupported_citation"}
        claim_lines = [
            line for line in answer.splitlines()
            if re.match(r"^\s*(?:[-*]|\d+[.)])\s+", line)
        ]
        if any(not re.search(r"\[\d+\]\s*$", line) for line in claim_lines):
            return {"answer": None, "sources": hits, "status": "unsupported_citation"}
        plain_answer = re.sub(r"[*_]", "", answer)
        if re.search(r"(?<![\d가-힣])개 이상", plain_answer):
            return {"answer": None, "sources": hits, "status": "malformed_quantity"}
        sources = [hit for i, hit in enumerate(hits, 1) if i in cited]
        return {"answer": answer, "sources": sources, "status": "answered"}

    generation = RunnablePassthrough.assign(answer=answer_chain) | RunnableLambda(package)
    return search_chain | RunnableBranch(
        (insufficient, RunnableLambda(no_evidence)), generation
    )

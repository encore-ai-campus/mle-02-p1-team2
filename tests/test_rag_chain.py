import unittest

from langchain_core.runnables import RunnableLambda

from src.rag_chain import UNKNOWN, build_rag_chain


HIT = {
    "doc_id": "GUIDE-1",
    "text": "사다리는 평탄하고 견고한 바닥에 설치한다.",
    "similarity": 0.8,
    "metadata": {
        "title": "검증 지침",
        "source_url": "https://example.org/guide",
        "page": 2,
    },
}


class RagAnswerValidationTests(unittest.TestCase):
    def check_status(self, response: str, expected: str) -> None:
        chain = build_rag_chain(
            lambda *args, **kwargs: [HIT], RunnableLambda(lambda _: response)
        )
        actual = chain.invoke({"question": "사다리 설치 방법은?"})
        self.assertEqual(actual["status"], expected)

    def test_rejects_uncited_claim(self) -> None:
        self.check_status(
            "- 사다리 상태를 점검하세요.\n- 평탄한 바닥에 설치하세요.[1]",
            "unsupported_citation",
        )

    def test_accepts_cited_claim(self) -> None:
        self.check_status("- 평탄한 바닥에 설치하세요.[1]", "answered")

    def test_rejects_missing_quantity(self) -> None:
        self.check_status(
            "- 사다리가 **개 이상의 버팀대**를 갖추는지 확인하세요.[1]",
            "malformed_quantity",
        )

    def test_abstains_when_model_says_unknown(self) -> None:
        self.check_status(UNKNOWN, "insufficient_evidence")

    def test_abstains_when_unknown_has_list_marker(self) -> None:
        self.check_status(f"- {UNKNOWN}", "insufficient_evidence")

    def test_exact_document_match_does_not_fail_similarity_threshold(self) -> None:
        exact_hit = {**HIT, "similarity": 0.01, "exact_doc_id_match": True}
        chain = build_rag_chain(
            lambda *args, **kwargs: [exact_hit],
            RunnableLambda(lambda _: "- 원문에 적힌 내용입니다.[1]"),
            min_similarity=0.9,
        )
        result = chain.invoke({"question": "GUIDE-1에서 확인되는 내용은?"})
        self.assertEqual(result["status"], "answered")

    def test_tbm_requires_both_source_types_to_be_cited(self) -> None:
        sif = {**HIT, "doc_id": "SIF-1", "metadata": {**HIT["metadata"], "source_type": "sif"}}
        guide = {**HIT, "doc_id": "GUIDE-1", "metadata": {**HIT["metadata"], "source_type": "kosha_guide"}}

        chain = build_rag_chain(
            lambda *args, **kwargs: [sif, guide],
            RunnableLambda(lambda _: "- [ ] 사고 확인.[1]\n- [ ] 지침 확인.[2]"),
        )
        result = chain.invoke({
            "question": "TBM 체크리스트",
            "required_source_types": ["sif", "kosha_guide"],
        })
        self.assertEqual(result["status"], "answered")
        self.assertEqual({hit["metadata"]["source_type"] for hit in result["sources"]}, {"sif", "kosha_guide"})

        one_source_chain = build_rag_chain(
            lambda *args, **kwargs: [sif, guide],
            RunnableLambda(lambda _: "- [ ] 사고 확인.[1]"),
        )
        rejected = one_source_chain.invoke({
            "question": "TBM 체크리스트",
            "required_source_types": ["sif", "kosha_guide"],
        })
        self.assertEqual(rejected["status"], "unsupported_citation")

    def test_kosha_guide_answer_gets_law_scope_note(self) -> None:
        guide = {
            **HIT,
            "metadata": {**HIT["metadata"], "source_type": "kosha_guide"},
        }
        chain = build_rag_chain(
            lambda *args, **kwargs: [guide],
            RunnableLambda(lambda _: "- 지침은 작업 전 확인을 안내합니다.[1]"),
        )
        result = chain.invoke({"question": "작업 전 무엇을 확인해?"})
        self.assertEqual(result["status"], "answered")
        self.assertIn("현행 법령과 일치한다고 단정하지 않습니다.[1]", result["answer"])

    def test_passes_work_context_and_filters(self) -> None:
        calls = []

        def retrieve(query, **kwargs):
            calls.append((query, kwargs))
            return [HIT]

        chain = build_rag_chain(
            retrieve, RunnableLambda(lambda _: "- 평탄한 바닥에 설치하세요.[1]")
        )
        result = chain.invoke({
            "question": "어떻게 설치해?",
            "work_context": "건설업 이동식 사다리 작업",
            "chat_history": [{"role": "user", "content": "사다리 작업 기준은?"}],
            "source_type": "kosha_guide",
            "industry_major": "건설업",
            "equipment": "사다리",
        })
        self.assertEqual(result["status"], "answered")
        self.assertIn("건설업 이동식 사다리 작업", calls[0][0])
        self.assertIn("사다리 작업 기준은?", calls[0][0])
        self.assertEqual(calls[0][1]["industry_major"], "건설업")
        self.assertEqual(calls[0][1]["equipment"], "사다리")


if __name__ == "__main__":
    unittest.main()

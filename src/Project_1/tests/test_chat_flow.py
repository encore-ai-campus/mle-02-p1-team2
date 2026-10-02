"""작업 표현이 사전에 없거나 후속 질문이어도 근거 흐름이 이어지는지 확인한다."""

import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import numpy as np
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

from services.query_analysis import analyze_query
from services.safety_rag import (
    GeneratedSafety, SafetyAnalysis, SafetyRAGService, is_followup, make_search_query,
)


VECTOR = [0.1] * 1536
SIF_DOC = Document(page_content="굴착기 작업 중 사고가 발생했다.", metadata={
    "source_id": "sif:test", "기인물": "굴착기", "재해유발요인": "충돌", "distance": 0.2,
})
KOSHA_DOC = Document(page_content="작업 전 안전조치를 확인한다.", metadata={
    "guide_id": "B-M-1", "title": "안전작업 지침", "section": "안전조치", "page": "1", "distance": 0.2,
})


def draft(*, sif=True, kosha=True):
    return GeneratedSafety(
        work_summary="현재 질문에 대한 직접 답변", sif_supported=sif, kosha_supported=kosha,
        hazards=[], sif_summary="관련 사고 요약", kosha_summary="관련 기준 요약",
        prevention=["근거에 따른 조치"], limitation="",
    )


def service(history=()):
    instance = object.__new__(SafetyRAGService)
    instance.sif_count = 1
    instance.kosha_count = 1
    instance.embeddings = Mock(embed_documents=Mock(side_effect=lambda texts: [VECTOR for _ in texts]))
    instance.answer_llm = Mock(invoke=Mock(return_value=draft()))
    instance.recent_history = Mock(return_value=list(history))
    instance.save_turn = Mock(return_value=True)
    instance.retrieve_sif = Mock(return_value=[SIF_DOC])
    instance.retrieve_kosha = Mock(return_value=[KOSHA_DOC])
    return instance


class ChatFlowTests(unittest.TestCase):
    def test_unknown_vocabulary_still_searches(self):
        context = analyze_query("제지 공장에서 나무를 가공할 때 위험은?")
        self.assertIn("제지", context.sif_query)
        self.assertIn("나무", context.sif_query)
        self.assertIn("제지", context.search_terms)
        self.assertIn("나무", context.search_terms)

        rag = service()
        rag.answer_llm.invoke.return_value = draft(kosha=False)
        rag.retrieve_kosha.return_value = []
        report = rag.ask("제지 공장에서 나무를 가공할 때 위험은?", str(uuid4()), [])
        rag.retrieve_sif.assert_called_once()
        rag.retrieve_kosha.assert_called_once()
        self.assertEqual(len(report.sif_cases), 1)

        known = analyze_query("굴착기로 터파기 작업을 할 때 무엇을 확인해야 하나?")
        self.assertIn("굴착기", known.topic)
        self.assertNotIn("확인해야", known.topic)

    def test_followup_reuses_sif_and_refreshes_kosha_for_new_intent(self):
        previous = SafetyAnalysis(topic="굴착기 터파기", intent="점검", sif_documents=[SIF_DOC],
                                  kosha_documents=[KOSHA_DOC])
        local = [{"role": "user", "content": "굴착기로 터파기 작업을 할 때 무엇을 확인해야 하나?"},
                 {"role": "assistant", "analysis": previous}]
        rag = service([HumanMessage(content=local[0]["content"]), AIMessage(content="이전 답변")])
        report = rag.ask("그럼 사고를 예방하려면?", str(uuid4()), local)
        rag.retrieve_sif.assert_not_called()
        rag.retrieve_kosha.assert_called_once()
        self.assertEqual(rag.embeddings.embed_documents.call_args.args[0], [
            "굴착기 터파기 사고 예방 안전조치 금지사항 작업방법"
        ])
        self.assertTrue(report.followup)
        self.assertTrue(report.debug["reused_evidence"]["sif"])
        self.assertEqual(report.sif_cases[0].source_id, "sif:test")

    def test_new_unlisted_topic_does_not_inherit_previous_equipment(self):
        history = [HumanMessage(content="굴착기 작업 안전은?")]
        self.assertFalse(is_followup("제지 공장에서 나무를 가공하려면?"))
        self.assertEqual(make_search_query("제지 공장에서 나무를 가공하려면?", history, "굴착기"),
                         "제지 공장에서 나무를 가공하려면?")
        self.assertFalse(is_followup("그럼 나무 절단 작업은?"))
        self.assertTrue(is_followup("그럼 사고를 예방하려면?"))

        previous = SafetyAnalysis(topic="굴착기 터파기", intent="점검", sif_documents=[SIF_DOC])
        local = [{"role": "user", "content": "굴착기 작업 안전은?"},
                 {"role": "assistant", "analysis": previous}]
        rag = service(history)
        report = rag.ask("제지 공장에서 나무를 가공하려면?", str(uuid4()), local)
        rag.retrieve_sif.assert_called_once()
        self.assertFalse(report.followup)
        self.assertIn("제지", report.search_query)
        self.assertNotIn("굴착기", report.search_query)

    def test_same_intent_followup_reuses_both_without_embedding(self):
        previous = SafetyAnalysis(topic="굴착기 터파기", intent="예방", sif_documents=[SIF_DOC],
                                  kosha_documents=[KOSHA_DOC])
        local = [{"role": "user", "content": "굴착기 사고를 예방하려면?"},
                 {"role": "assistant", "analysis": previous}]
        rag = service([HumanMessage(content=local[0]["content"]), AIMessage(content="이전 답변")])
        report = rag.ask("그중 중요한 건?", str(uuid4()), local)
        rag.embeddings.embed_documents.assert_not_called()
        rag.retrieve_sif.assert_not_called()
        rag.retrieve_kosha.assert_not_called()
        self.assertEqual(len(report.kosha_guides), 1)

    def test_third_crane_question_keeps_topic_and_refreshes_checklist(self):
        self.assertTrue(is_followup("그러면 뭐 점검하면 되는데?"))
        self.assertTrue(is_followup("그럼 점검하면?"))
        self.assertTrue(is_followup("그럼 뭘 작업 전에 확인해?"))
        first = SafetyAnalysis(topic="크레인 작업 주의사항", intent="일반",
                               sif_documents=[SIF_DOC], kosha_documents=[KOSHA_DOC])
        second = SafetyAnalysis(topic="크레인 작업 주의사항", intent="일반",
                                sif_documents=[SIF_DOC], kosha_documents=[KOSHA_DOC])
        local = [
            {"role": "user", "content": "크레인 작업 주의사항"},
            {"role": "assistant", "analysis": first},
            {"role": "user", "content": "그중 가장 중요한 건?"},
            {"role": "assistant", "analysis": second},
        ]
        history = [HumanMessage(content=local[0]["content"]), AIMessage(content="첫 답변"),
                   HumanMessage(content=local[2]["content"]), AIMessage(content="둘째 답변")]
        rag = service(history)
        report = rag.ask("그러면 뭐 점검하면 되는데?", str(uuid4()), local)
        self.assertTrue(report.followup)
        self.assertEqual(report.topic, "크레인 작업 주의사항")
        self.assertIn("크레인", report.search_query)
        rag.retrieve_sif.assert_not_called()
        rag.retrieve_kosha.assert_called_once()
        self.assertEqual(len(report.kosha_guides), 1)

    def test_followup_can_recover_evidence_from_earlier_turn(self):
        first = SafetyAnalysis(topic="크레인 작업 주의사항", intent="점검",
                               sif_documents=[SIF_DOC], kosha_documents=[KOSHA_DOC])
        second = SafetyAnalysis(topic="크레인 작업 주의사항", intent="일반")
        local = [{"role": "assistant", "analysis": first},
                 {"role": "user", "content": "그중 가장 중요한 건?"},
                 {"role": "assistant", "analysis": second}]
        rag = service([HumanMessage(content="크레인 작업 주의사항")])
        report = rag.ask("그러면 뭐 점검하면 되는데?", str(uuid4()), local)
        rag.embeddings.embed_documents.assert_not_called()
        self.assertTrue(report.debug["reused_evidence"]["sif"])
        self.assertTrue(report.debug["reused_evidence"]["kosha"])
        self.assertEqual(len(report.kosha_guides), 1)

    def test_old_failed_third_turn_does_not_replace_crane_topic(self):
        first = SafetyAnalysis(topic="크레인 작업 주의사항", intent="일반",
                               sif_documents=[SIF_DOC], kosha_documents=[KOSHA_DOC])
        failed = SafetyAnalysis(topic="뭐 점검하면 되는데", intent="점검")
        local = [{"role": "user", "content": "크레인 작업 주의사항"},
                 {"role": "assistant", "analysis": first},
                 {"role": "user", "content": "그중 가장 중요한 건?"},
                 {"role": "assistant", "analysis": first},
                 {"role": "user", "content": "그러면 뭐 점검하면 되는데?"},
                 {"role": "assistant", "analysis": failed}]
        rag = service([HumanMessage(content="크레인 작업 주의사항")])
        report = rag.ask("작업 전에는 뭘 확인해?", str(uuid4()), local)
        self.assertEqual(report.topic, "크레인 작업 주의사항")
        self.assertTrue(report.followup)
        self.assertEqual(len(report.kosha_guides), 1)

    def test_unknown_kosha_category_requires_source_word_match(self):
        rag = object.__new__(SafetyRAGService)
        unrelated = Document(page_content="지게차 적재 작업", metadata={"title": "지게차 안전"})
        relevant = Document(page_content="나무 절단 작업 시 점검", metadata={"title": "목재 작업"})
        rag.kosha_store = Mock()
        rag.kosha_store.similarity_search_with_score_by_vector.return_value = [
            (unrelated, 0.2), (relevant, 0.3),
        ]
        context = analyze_query("나무를 절단할 때 주의할 점은?")
        documents = rag.retrieve_kosha(np.ones(1536, dtype=np.float32), context)
        self.assertEqual(len(documents), 1)
        self.assertIn("나무", documents[0].page_content)

    def test_empty_db_history_uses_current_screen_messages(self):
        rag = object.__new__(SafetyRAGService)
        local = [{"role": "user", "content": "굴착기 작업은?"},
                 {"role": "assistant", "analysis": SafetyAnalysis(work_summary="사고 요약") }]
        with patch("services.safety_rag.psycopg.connect"), \
             patch("services.safety_rag.PostgresChatMessageHistory") as history_store:
            history_store.return_value.messages = []
            messages = rag.recent_history(str(uuid4()), local)
        self.assertEqual([type(message) for message in messages], [HumanMessage, AIMessage])


if __name__ == "__main__":
    unittest.main()

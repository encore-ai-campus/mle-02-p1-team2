"""Meaningful offline checks for routing loop, grounding and statistics safety."""
import json
import unittest
from unittest.mock import Mock, patch

import pandas as pd
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, ToolMessage

from preventra_agent.agent import SafetyAgent
from preventra_agent.models import ConversationTurn
from preventra_agent.tools import SafetyTools


def final(text="안녕하세요!", refs=()):
    return AIMessage(content=json.dumps({"final_answer": text, "evidence_ids": list(refs)}, ensure_ascii=False))


def call(name, args, call_id="call-1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}])


class Model:
    def __init__(self, *replies):
        self.replies = iter(replies)
        self.requests = []

    def bind_tools(self, tools, **kwargs):
        self.schemas = [t.args_schema.model_json_schema() for t in tools]
        return self

    def invoke(self, messages):
        self.requests.append(list(messages))
        return next(self.replies)


def statistics():
    return pd.DataFrame([
        (year, "건설업", "건설업", size, metric, value)
        for year in (2020, 2022, 2025)
        for size in ("5인 미만", "5-9인")
        for metric, value in (("사고사망자수", 4.0), ("사망만인율", 1.2))
    ], columns=["연도", "대업종", "산업중분류", "규모", "지표", "값"])


class AgentTests(unittest.TestCase):
    def setUp(self):
        patch("preventra_agent.observability.get_tracing_client", return_value=None).start()
        self.addCleanup(patch.stopall)

    def backend(self):
        self.rag = Mock()
        self.rag.embeddings.embed_query.return_value = [0.0] * 1536
        self.rag.retrieve_sif.return_value = [Document(page_content="지게차 충돌 사례. 위험성 감소대책(예시): 추정 대책", metadata={"source_id": "sif-1", "기인물": "지게차", "재해유발요인": "충돌", "source_file": "test.xlsx", "sheet": "제조업", "row_number": 1})]
        self.rag.retrieve_kosha.return_value = [Document(page_content="작업 전 장치 확인", metadata={"guide_id": "TEST-GUIDE", "title": "테스트 가이드", "section": "점검", "page": "3"})]
        self.factory = Mock(return_value=self.rag)
        self.loader = Mock(return_value=statistics())
        return SafetyTools(self.factory, self.loader)

    def test_greeting_never_initializes_retrieval_or_statistics(self):
        backend = self.backend()
        result = SafetyAgent(Model(final()), backend).run("안녕")
        self.assertEqual(result.used_tools, [])
        self.factory.assert_not_called()
        self.loader.assert_not_called()

    def test_sif_only_reuses_service_and_keeps_metadata(self):
        backend = self.backend()
        model = Model(call("search_sif_cases", {"query": "지게차 충돌 사고사례"}), final("지게차 충돌 사례입니다. [SIF-1]", ["SIF-1"]))
        result = SafetyAgent(model, backend).run("지게차 충돌 사고사례")
        self.assertEqual(result.used_tools, ["search_sif_cases"])
        self.rag.retrieve_kosha.assert_not_called()
        self.rag.ask.assert_not_called()
        self.rag.save_turn.assert_not_called()
        self.assertEqual(result.evidence[0].source["doc_id"], "sif-1")
        self.assertNotIn("추정 대책", result.evidence[0].excerpt)
        self.assertTrue(any(isinstance(m, ToolMessage) for m in model.requests[-1]))

    def test_followup_carries_both_sides_and_calls_only_guide(self):
        backend = self.backend()
        model = Model(call("search_kosha_guides", {"query": "지게차 자재 운반 작업 전 확인"}), final("작업 전 장치를 확인합니다. [GUIDE-1]", ["GUIDE-1"]))
        history = (ConversationTurn("지게차로 자재를 운반 중이야", "어떤 정보가 필요하신가요?"),)
        result = SafetyAgent(model, backend).run("그럼 작업 전에는 뭘 확인해야 해?", history)
        self.assertEqual(result.used_tools, ["search_kosha_guides"])
        self.rag.retrieve_sif.assert_not_called()
        self.assertEqual([m.content for m in model.requests[0][1:3]], [history[0].question, history[0].final_answer])

    def test_combined_returns_only_cited_candidates(self):
        backend = self.backend()
        model = Model(call("search_sif_cases", {"query": "지게차 실제 사고"}),
                      call("search_kosha_guides", {"query": "지게차 예방방법"}, "call-2"),
                      final("가이드의 장치를 확인하세요. [GUIDE-1]", ["GUIDE-1"]))
        result = SafetyAgent(model, backend).run("지게차 사고와 예방")
        self.assertEqual(len(result.used_tools), 2)
        self.assertEqual([e.kind for e in result.evidence], ["guide"])

    def test_fabricated_citation_fails_closed(self):
        result = SafetyAgent(Model(final("가짜 [GUIDE-99]", ["GUIDE-99"])), self.backend()).run("질문")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.evidence, [])
        self.assertNotIn("가짜", result.final_answer)

    def test_partial_failure_retains_successful_other_source(self):
        backend = self.backend()
        self.rag.retrieve_sif.side_effect = RuntimeError("private-secret")
        model = Model(call("search_sif_cases", {"query": "지게차 사고"}), call("search_kosha_guides", {"query": "지게차 점검"}, "call-2"), final("사고 검색은 실패했습니다. 장치를 확인하세요. [GUIDE-1]", ["GUIDE-1"]))
        result = SafetyAgent(model, backend).run("사고와 점검")
        self.assertEqual(result.status, "ready")
        self.assertEqual([r.status for r in result.tool_results], ["error", "ok"])
        self.assertNotIn("private-secret", str(result))

    def test_tool_exception_is_reported_as_failure_not_invalid_input(self):
        class BrokenTool:
            name = "search_sif_cases"
            args_schema = type("Schema", (), {"model_json_schema": staticmethod(lambda: {})})

            def invoke(self, call, config=None):
                raise RuntimeError("private-secret")

        class BrokenBackend:
            def build(self):
                return [BrokenTool()]

        model = Model(call("search_sif_cases", {"query": "query"}), final())
        result = SafetyAgent(model, BrokenBackend()).run("query")
        self.assertEqual(result.tool_results[0].status, "error")
        self.assertNotIn("private-secret", str(result))

    def test_duplicate_call_is_not_executed_twice(self):
        backend = self.backend()
        model = Model(call("search_sif_cases", {"query": "지게차 사고"}), call("search_sif_cases", {"query": "지게차 사고"}, "call-2"), final("사례 [SIF-1]", ["SIF-1"]))
        result = SafetyAgent(model, backend).run("사례")
        self.rag.retrieve_sif.assert_called_once()
        self.assertEqual(len(result.trace), 1)

    def test_response_only_parsed_arguments_are_not_replayed(self):
        backend = self.backend()
        reply = call("search_sif_cases", {"query": "지게차 사고"})
        reply.content = [{"type": "function_call", "parsed_arguments": {"query": "지게차 사고"}}]
        model = Model(reply, final("사례 [SIF-1]", ["SIF-1"]))
        result = SafetyAgent(model, backend).run("사례")
        replay = model.requests[-1][2]
        self.assertEqual(replay.content, "")
        self.assertEqual(replay.additional_kwargs, {})
        self.assertEqual(result.status, "ready")

    def test_rate_requires_single_industry_and_size(self):
        backend = self.backend()
        self.assertEqual(backend.snapshot("사망만인율", "건설업", None, 2025).status, "needs_clarification")
        self.assertEqual(backend.trend("사망만인율", None, None, None, None).status, "needs_clarification")
        rate = backend.snapshot("사망만인율", "건설업", "5인 미만", 2025)
        self.assertEqual(rate.data["value"], 1.2)

    def test_trend_preserves_missing_years_and_actual_scope(self):
        result = self.backend().trend("사고사망자수", "건설업", None, 2020, 2025)
        self.assertEqual(result.data["missing_years"], [2021, 2023, 2024])
        self.assertIsNone(result.data["records"][1]["value"])
        self.assertEqual(result.data["records"][0]["value"], 8)
        self.assertFalse(result.figures[0].data[0].connectgaps)
        self.assertEqual(result.evidence[0].source["years"], [2020, 2022, 2025])

    def test_unknown_industry_and_unavailable_year_not_substituted(self):
        backend = self.backend()
        self.assertEqual(backend.snapshot("사고사망자수", "제조업", None, 2025).status, "needs_clarification")
        self.assertEqual(backend.snapshot("사고사망자수", "건설업", None, 2026).status, "empty")


if __name__ == "__main__":
    unittest.main()

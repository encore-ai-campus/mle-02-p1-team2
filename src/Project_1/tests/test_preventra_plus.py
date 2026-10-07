"""Offline regression checks for the isolated work-plan integration."""
from dataclasses import replace
from datetime import timedelta
from io import BytesIO
import json
import unittest
from unittest.mock import patch

from openpyxl import Workbook
from langchain_core.messages import AIMessage

from preventra_plan import domain
from preventra_plan.agent import PlanTools, dispatch
from preventra_ui import gateway
from preventra_ui.history import encode_result, decode_result
from preventra_agent.agent import SafetyAgent
from preventra_agent.models import AgentResult, Evidence as AgentEvidence
from test_preventra_agent import Model, call, final


def workbook_bytes():
    day = domain.today_korea().isoformat()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "계획"
    sheet.append(["현장명", "테스트 현장"])
    sheet.append(["현장지역", "민감 주소"])
    sheet.append(list(domain.HEADERS))
    sheet.append(["A", day, "09:00", "11:00", "1구역", "민감 상세 위치", "운반",
                  "지게차 자재 운반", "지게차", 2, "민감 업체", "민감 담당자",
                  "보행 통로 구분", "작업구역 확인", "", ""])
    sheet.append(["B", day, "10:00", "12:00", "1구역", "", "정리", "자재 정리",
                  "", None, "", "", "", "", "", ""])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def work_context():
    plan = domain.read_work_plan(workbook_bytes())
    return {"work_plan": domain.snapshot(plan, domain.today_korea())}


class WorkPlanIntegrationTests(unittest.TestCase):
    def test_snapshot_roundtrip_keeps_only_required_plan_details(self):
        plan = domain.read_work_plan(workbook_bytes())
        value = domain.encode_plan(plan)
        serialized = json.dumps(value, ensure_ascii=False)
        for private_value in ("민감 주소", "민감 상세 위치", "민감 업체", "민감 담당자"):
            self.assertNotIn(private_value, serialized)
        decoded = domain.decode_plan(value)
        self.assertEqual(decoded.items[0].owner, "기재됨")
        self.assertNotIn("작업책임자", domain.missing_work_fields(decoded.items[0]))
        self.assertEqual(len(domain.coordination_candidates(plan.items, domain.today_korea())), 1)

    def test_plan_tool_returns_grounded_rows_without_personal_fields(self):
        tools = PlanTools(work_context())
        result = tools.plan_result(None, None)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.data["work_count"], 2)
        body = json.dumps(result.model_payload(), ensure_ascii=False)
        for private_value in ("민감 업체", "민감 담당자", "민감 상세 위치", "민감 주소"):
            self.assertNotIn(private_value, body)
        tomorrow = (domain.today_korea() + timedelta(days=1)).isoformat()
        self.assertEqual(tools.plan_result(tomorrow, None).status, "empty")
        self.assertEqual(PlanTools({}).plan_result(None, None).status, "empty")
        self.assertEqual(len(tools.build()), 5)

    def test_plan_citation_and_result_history_roundtrip(self):
        ctx = work_context()
        backend = PlanTools(ctx)
        model = Model(call("get_work_plan", {"day": None, "work_id": "A", "period": None}),
                      final("계획에는 보행 통로 구분이 적혀 있습니다. [PLAN-1]", ["PLAN-1"]))
        with patch("preventra_agent.observability.get_tracing_client", return_value=None):
            result = SafetyAgent(model, backend).run("오늘 계획된 안전조치")
        self.assertEqual(result.status, "ready")
        self.assertEqual([item.reference for item in result.evidence], ["PLAN-1"])
        ui_result = gateway.dispatch(
            gateway.AssistantRequest("req", "session", "질문"),
            agent=type("FakeAgent", (), {"run": lambda *args, **kwargs: result})())
        self.assertEqual(len(ui_result.plan_sources), 1)
        self.assertEqual(ui_result.guides, [])
        self.assertEqual(decode_result(encode_result(ui_result), "").plan_sources, ui_result.plan_sources)

    def test_fabricated_plan_citation_fails_closed(self):
        with patch("preventra_agent.observability.get_tracing_client", return_value=None):
            result = SafetyAgent(Model(final("가짜 [PLAN-99]", ["PLAN-99"])),
                                 PlanTools(work_context())).run("계획")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.evidence, [])

    def test_plan_dispatch_injects_selected_date_and_uses_existing_gateway(self):
        ctx = work_context()
        ctx["work_plan"]["day"] = "2026-10-12"
        request = gateway.AssistantRequest("r", "s", "오늘 계획은?", context=ctx)
        with patch("preventra_plan.agent.SafetyAgent") as factory, \
             patch("preventra_ui.gateway.dispatch") as existing:
            dispatch(request)
        self.assertIn("계획 기준일은 2026-10-12", factory.call_args.kwargs["system_prompt"])
        self.assertIs(existing.call_args.args[0], request)

    def test_without_plan_delegates_to_current_agent_flow(self):
        request = gateway.AssistantRequest("r", "s", "통계")
        with patch("preventra_ui.gateway.dispatch", return_value=gateway.AssistantResult(answer="기존")) as existing:
            result = dispatch(request)
        self.assertEqual(result.answer, "기존")
        existing.assert_called_once_with(request)


if __name__ == "__main__":
    unittest.main()

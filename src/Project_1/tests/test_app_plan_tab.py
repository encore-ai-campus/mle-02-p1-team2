from pathlib import Path
import unittest
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
from preventra_fakes import MemoryStore
from preventra_plan.storage import SavedPlan
from preventra_ui.gateway import AssistantResult

ROOT = Path(__file__).resolve().parents[3]

def fixture():
    return pd.DataFrame([(2025, "건설업", "건설업", "5인 미만", metric, value)
        for metric, value in (("사고재해자수", 10), ("사고사망자수", 1), ("사망만인율", 1.0))],
        columns=["연도", "대업종", "산업중분류", "규모", "지표", "값"])

class EmptyPlans:
    def load(self, identifier):
        return SavedPlan()

class ActiveAppPlanTabTests(unittest.TestCase):
    def setUp(self):
        self.store=MemoryStore()
        self.dispatch=patch("preventra_plan.agent.dispatch",
            return_value=AssistantResult(answer="계획 상담 응답")).start()
        patch("preventra_ui.state.get_store", return_value=self.store).start()
        patch("preventra_plan.ui.get_plan_store", return_value=EmptyPlans()).start()
        patch("services.statistics.load_statistics", return_value=fixture()).start()
        self.addCleanup(patch.stopall)

    def test_active_app_keeps_existing_tabs_and_routes_plan_questions(self):
        app=AppTest.from_file(str(ROOT/"src"/"Project_1"/"app.py"), default_timeout=20).run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual([tab.label for tab in app.tabs],
            ["🦺 작업 안전 상담","📋 작업계획 상담","📊 산업재해 현황"])
        self.assertEqual(len(app.get("file_uploader")),1)
        app.text_input("plan_question").set_value("오늘 계획을 확인해 줘")
        app.button("plan_question_submit").click().run()
        self.assertEqual(len(app.exception),0)
        self.dispatch.assert_called_once()
        request=self.dispatch.call_args.args[0]
        self.assertEqual(request.question,"오늘 계획을 확인해 줘")
        self.assertEqual(request.context,{})

if __name__=="__main__":
    unittest.main()

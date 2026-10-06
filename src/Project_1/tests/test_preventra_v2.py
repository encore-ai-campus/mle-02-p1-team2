"""Integrated UI regression checks, with existing store/result fixtures."""
from pathlib import Path
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from preventra_ui.gateway import AssistantResult, Evidence
from preventra_fakes import MemoryStore
from test_preventra_ui import fixture

ENTRY = Path(__file__).resolve().parents[1] / "Preventra_v2.py"


class IntegratedUITests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        patch("preventra_ui.state.get_store", return_value=self.store).start()
        self.loader = patch("preventra_ui.statistics_view.get_statistics", return_value=fixture()).start()
        self.dispatch = patch("preventra_ui.gateway.dispatch", return_value=AssistantResult(answer="검증용 응답")).start()
        self.addCleanup(patch.stopall)

    def app(self):
        app = AppTest.from_file(str(ENTRY), default_timeout=20).run()
        self.assertFalse(app.exception)
        return app

    def click(self, app, key):
        app.button(key).click().run()
        self.assertFalse(app.exception)

    def submit(self, app, question="지게차 작업 질문"):
        app.text_area("preventra_home_question").set_value(question)
        next(b for b in app.button if b.label == "질문 보내기").click().run()
        self.assertFalse(app.exception)

    def test_home_retains_full_statistics_and_removes_extra_navigation(self):
        app = self.app()
        self.assertEqual([m.value for m in app.metric], ["200명", "4명"])
        self.assertEqual(len(app.get("plotly_chart")), 1)
        self.assertFalse(any(b.label == "안전 질문하기" for b in app.button))
        self.assertEqual(len(app.sidebar.selectbox), 0)

    def test_submit_and_rerun_do_not_repeat_dispatch(self):
        app = self.app()
        self.submit(app)
        app.run().run()
        self.dispatch.assert_called_once()
        self.assertEqual([m.name for m in app.chat_message], ["user", "assistant"])

    def test_home_is_non_destructive_and_home_question_starts_new_conversation(self):
        app = self.app()
        self.submit(app)
        first = app.session_state["preventra_conversation_id"]
        self.click(app, "pv2_nav_홈")
        self.assertEqual(app.session_state["preventra_conversation_id"], first)
        self.assertEqual(len(self.store.rows), 1)
        self.submit(app, "고소작업 점검")
        self.assertNotEqual(app.session_state["preventra_conversation_id"], first)
        self.click(app, "preventra_conversation_" + first)
        self.assertEqual(app.chat_message[0].markdown[0].value, "지게차 작업 질문")
        app.chat_input[0].set_value("그럼 작업 전에는?").run()
        self.assertEqual(len(self.store.load(first)), 2)
        self.assertEqual(self.dispatch.call_args.args[0].history[0].question, "지게차 작업 질문")

    def test_sources_reuses_loaded_coverage_and_original_descriptions(self):
        app = self.app()
        self.click(app, "pv2_nav_데이터·출처")
        self.assertEqual(len(app.dataframe), 1)
        self.assertTrue(any("SIF" in m.value for m in app.subheader))
        self.assertTrue(any("KOSHA GUIDE" in m.value for m in app.subheader))
        self.dispatch.assert_not_called()

    def test_empty_question_and_missing_statistics(self):
        self.loader.return_value = fixture().iloc[:0]
        app = self.app()
        self.assertTrue(any("통계가 없습니다" in n.value for n in app.info))
        self.submit(app, "   ")
        self.dispatch.assert_not_called()
        self.assertEqual(len(self.store.rows), 0)

    def test_unsaved_answer_cannot_be_lost_by_starting_from_home(self):
        app = self.app()
        self.store.fail_save = True
        self.submit(app)
        current = app.session_state["preventra_conversation_id"]
        self.click(app, "pv2_nav_홈")
        self.submit(app, "새 질문")
        self.assertEqual(app.session_state["preventra_conversation_id"], current)
        self.assertEqual(len(self.store.rows), 1)
        self.dispatch.assert_called_once()
        self.store.fail_save = False
        self.click(app, "preventra_retry_save")
        self.assertIsNone(app.session_state["preventra_unsaved"])

    def test_optional_evidence_and_literal_user_content(self):
        self.dispatch.return_value = AssistantResult(answer="가이드 응답", guides=[Evidence("가이드", "test", "본문")])
        app = self.app()
        payload = '<script>alert("test")</script>'
        self.submit(app, payload)
        self.assertEqual(len(app.expander), 1)
        self.assertEqual(len(app.get("plotly_chart")), 0)
        self.assertEqual(app.chat_message[0].markdown[0].value, payload)
        self.assertFalse(app.chat_message[0].markdown[0].proto.allow_html)

    def test_service_error_and_empty_chat(self):
        self.loader.side_effect = RuntimeError("private-secret")
        self.dispatch.side_effect = RuntimeError("private-secret")
        app = self.app()
        self.click(app, "preventra_new_chat")
        self.assertEqual(len(app.chat_message), 0)
        self.click(app, "pv2_empty_지게차 사고사례")
        app.run()
        self.dispatch.assert_called_once()
        self.assertFalse(any("private-secret" in n.value for n in app.warning))

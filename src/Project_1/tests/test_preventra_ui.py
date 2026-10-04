"""Offline UI integration checks: no DB or model requests."""
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from preventra_ui.gateway import AssistantResult, Evidence
from preventra_fakes import MemoryStore

ENTRY = Path(__file__).resolve().parents[1] / "Preventra.py"


def fixture():
    return pd.DataFrame([
        (year, "건설업", "건설업", size, metric, value)
        for year in (2023, 2025)
        for size in ("5인 미만", "5-9인")
        for metric, value in (("사고재해자수", 100), ("사고사망자수", 2), ("사망만인율", 1.5))
    ], columns=["연도", "대업종", "산업중분류", "규모", "지표", "값"])


class PreventraUITests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        patch("preventra_ui.state.get_store", return_value=self.store).start()
        self.loader = patch("preventra_ui.statistics_view.get_statistics", return_value=fixture()).start()
        self.dispatch = patch("preventra_ui.gateway.dispatch", return_value=AssistantResult(answer="테스트 일반 응답")).start()
        self.addCleanup(patch.stopall)

    def app(self):
        app = AppTest.from_file(str(ENTRY), default_timeout=15).run()
        self.assertEqual(len(app.exception), 0)
        return app

    def click(self, app, key):
        app.button(key).click().run()
        self.assertEqual(len(app.exception), 0)

    def test_home_form_handoff_and_rerun(self):
        app = self.app()
        app.text_input("preventra_home_question").input("  지게차 점검은?  ")
        next(b for b in app.button if b.label.startswith("안전 어시스턴트에서")).click().run()
        self.assertEqual(app.session_state["preventra_page"], "안전 어시스턴트")
        self.assertEqual(app.chat_message[0].markdown[0].value, "지게차 점검은?")
        app.run().run()
        self.assertEqual(len([m for m in app.chat_message if m.name == "user"]), 1)
        self.dispatch.assert_called_once()

    def test_each_example_is_forwarded_verbatim(self):
        for example in ("지게차 사고사례", "고소작업 전 확인사항", "우리 업종의 사고 추이"):
            with self.subTest(example=example):
                app = self.app()
                self.click(app, f"preventra_example_{example}")
                self.assertEqual(app.chat_message[0].markdown[0].value, example)

    def test_home_navigation_keeps_chat_new_chat_clears(self):
        app = self.app()
        self.click(app, "preventra_example_지게차 사고사례")
        session = app.session_state["preventra_session_id"]
        self.click(app, "preventra_sidebar_home")
        self.assertEqual(app.session_state["preventra_session_id"], session)
        self.click(app, "preventra_nav_데이터·출처")
        self.assertEqual(len(app.dataframe), 1)
        self.click(app, "preventra_nav_안전 어시스턴트")
        self.assertEqual(len([m for m in app.chat_message if m.name == "user"]), 1)
        self.click(app, "preventra_new_chat")
        self.assertNotEqual(app.session_state["preventra_session_id"], session)
        self.assertEqual(len([m for m in app.chat_message if m.name == "user"]), 0)
        self.assertIsNone(app.session_state["preventra_pending"])

    def test_followup_and_intentional_repeat_are_distinct_events(self):
        app = self.app()
        self.click(app, "preventra_example_지게차 사고사례")
        app.chat_input[0].set_value("지게차 사고사례").run()
        app.run()
        self.assertEqual(len([m for m in app.chat_message if m.name == "user"]), 2)
        self.assertEqual(self.dispatch.call_count, 2)
        request = self.dispatch.call_args.args[0]
        self.assertEqual(request.previous_questions, ("지게차 사고사례",))

    def test_whitespace_never_dispatches(self):
        app = self.app()
        app.text_input("preventra_home_question").input("   ")
        next(b for b in app.button if b.label.startswith("안전 어시스턴트에서")).click().run()
        self.assertEqual(app.session_state["preventra_page"], "홈")
        self.assertTrue(any("질문을 입력" in item.value for item in app.info))
        self.dispatch.assert_not_called()

    def test_statistics_counts_and_missing_year_notice(self):
        app = self.app()
        self.assertEqual([metric.value for metric in app.metric], ["200명", "4명"])
        self.assertEqual(len(app.get("plotly_chart")), 1)
        self.assertTrue(any("자료가 없는 연도" in caption.value for caption in app.caption))
        self.assertEqual(len(app.sidebar.selectbox), 0)
        self.assertEqual(len(app.sidebar.button), 2)

    def test_empty_statistics_keeps_navigation_available(self):
        self.loader.return_value = fixture().iloc[:0]
        app = self.app()
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("통계가 없습니다" in item.value for item in app.info))
        self.click(app, "preventra_example_고소작업 전 확인사항")
        self.assertEqual(len([m for m in app.chat_message if m.name == "user"]), 1)

    def test_storage_error_has_safe_notice_and_working_chat(self):
        self.loader.side_effect = RuntimeError("secret-do-not-display")
        app = self.app()
        self.assertTrue(any("통계를 불러오지" in item.value for item in app.warning))
        self.assertFalse(any("secret-do-not-display" in item.value for item in app.warning))
        self.click(app, "preventra_nav_안전 어시스턴트")
        self.assertEqual(len(app.chat_input), 1)

    def test_general_answer_has_no_empty_evidence_sections(self):
        app = self.app()
        self.click(app, "preventra_example_지게차 사고사례")
        self.assertEqual([m.name for m in app.chat_message], ["user", "assistant"])
        self.assertEqual(len(app.expander), 0)
        self.assertEqual(len(app.get("plotly_chart")), 0)
        self.assertEqual(app.chat_message[1].markdown[0].value, "테스트 일반 응답")

    def test_result_sections_are_optional(self):
        self.dispatch.return_value = AssistantResult(status="ready", answer="테스트 전용 응답", guides=[Evidence("테스트 가이드", "fixture", "테스트 본문", "p.1")])
        app = self.app()
        self.click(app, "preventra_example_지게차 사고사례")
        self.assertEqual(len(app.expander), 1)
        self.assertEqual(len(app.get("plotly_chart")), 0)
        self.assertFalse(any("관련 사고사례" == item.value for item in app.markdown))

    def test_dispatch_error_does_not_replay_on_rerun(self):
        self.dispatch.side_effect = RuntimeError("secret-do-not-display")
        app = self.app()
        self.click(app, "preventra_example_지게차 사고사례")
        app.run()
        self.assertEqual(len([m for m in app.chat_message if m.name == "user"]), 1)
        self.dispatch.assert_called_once()
        self.assertTrue(any("답변을 처리하지 못했습니다" in item.value for item in app.warning))

    def test_failed_answer_preserves_user_topic_for_followup(self):
        self.dispatch.side_effect = RuntimeError("temporary")
        app = self.app()
        self.click(app, "preventra_example_지게차 사고사례")
        self.dispatch.side_effect = None
        self.dispatch.return_value = AssistantResult(answer="테스트 후속 응답")
        app.chat_input[0].set_value("그럼 작업 전에는?").run()
        request = self.dispatch.call_args.args[0]
        self.assertEqual(request.history[0].question, "지게차 사고사례")
        self.assertEqual(request.history[0].final_answer, "이전 답변을 완료하지 못했습니다.")


if __name__ == "__main__":
    unittest.main()

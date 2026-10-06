"""Offline UI persistence contract, restore fidelity and failure recovery."""
from unittest.mock import patch
import unittest

import plotly.graph_objects as go

from preventra_ui.gateway import AssistantResult, Evidence
from preventra_ui.history import decode_result, encode_result, title_from_question
import test_preventra_ui as ui


class ConversationUITests(unittest.TestCase):
    setUp = ui.PreventraUITests.setUp
    app = ui.PreventraUITests.app
    click = ui.PreventraUITests.click
    def test_two_conversations_home_restore_and_followup(self):
        app = self.app()
        self.assertEqual(len(self.store.rows), 0)
        self.click(app, "preventra_new_chat")
        first = app.session_state["preventra_conversation_id"]
        app.chat_input[0].set_value("지게차로 자재를 운반 중이야").run()
        self.click(app, "preventra_new_chat")
        second = app.session_state["preventra_conversation_id"]
        self.assertNotEqual(first, second)
        self.click(app, "preventra_sidebar_home")
        self.assertEqual(len(self.store.rows), 2)
        self.assertEqual(app.session_state["preventra_conversation_id"], second)
        self.assertEqual(len(app.session_state["preventra_recent"]), 2)
        # A fresh Streamlit session uses only the DB substitute, never old UI state.
        app = self.app()
        self.click(app, f"preventra_conversation_{first}")
        self.assertEqual(len(app.chat_message), 2)
        app.chat_input[0].set_value("그럼 작업 전에는?").run()
        request = self.dispatch.call_args.args[0]
        self.assertEqual(request.session_id, first)
        self.assertEqual(request.history[0].question, "지게차로 자재를 운반 중이야")
        self.assertEqual(len(self.store.load(first)), 2)
        self.assertEqual(len(self.store.load(second)), 0)
        self.assertEqual(self.store.list_recent()[0].conversation_id, first)

    def test_save_failure_retry_never_reexecutes_agent(self):
        app = self.app()
        self.store.fail_save = True
        self.click(app, "preventra_example_지게차 사고사례")
        first = app.session_state["preventra_conversation_id"]
        self.assertIsNotNone(app.session_state["preventra_unsaved"])
        self.assertTrue(app.chat_input[0].disabled)
        self.click(app, "preventra_new_chat")
        self.assertEqual(app.session_state["preventra_conversation_id"], first)
        self.assertEqual(len(self.store.load(first)), 0)
        self.store.fail_save = False
        self.click(app, "preventra_retry_save")
        app.run()
        self.assertEqual(len(self.store.load(first)), 1)
        self.assertIsNone(app.session_state["preventra_unsaved"])
        self.dispatch.assert_called_once()
        self.assertFalse(any("private-connection-string" in w.value for w in app.warning))

    def test_db_unavailable_never_fakes_durable_conversation(self):
        with patch("preventra_ui.state.get_store", side_effect=RuntimeError("password=private")):
            app = self.app()
            self.click(app, "preventra_new_chat")
            self.assertIsNone(app.session_state["preventra_conversation_id"])
            self.assertTrue(app.warning)
            self.dispatch.assert_not_called()
            self.assertFalse(any("password" in w.value for w in app.warning))

    def test_chart_and_evidence_restore_without_model_or_data_reload(self):
        evidence = Evidence("가이드", "fixture", "점검", reference="GUIDE-1", source={"page": "2"})
        self.dispatch.return_value = AssistantResult(answer="답변", guides=[evidence],
            figures=[go.Figure(go.Scatter(x=[2020, 2022], y=[1, 2]))], statistics_caption="출처")
        app = self.app()
        self.click(app, "preventra_example_지게차 사고사례")
        first = app.session_state["preventra_conversation_id"]
        restored = self.app()
        self.click(restored, f"preventra_conversation_{first}")
        self.assertEqual(len(restored.expander), 1)
        self.assertEqual(len(restored.get("plotly_chart")), 1)
        self.dispatch.assert_called_once()

    def test_title_and_snapshot_contract(self):
        title = title_from_question("\n  지게차 " + "점검 " * 30)
        self.assertLessEqual(len(title), 32)
        self.assertTrue(title.endswith("…"))
        result = AssistantResult(answer="answer", trace=[{"private": "not persisted"}], tool_results=[object()])
        payload = encode_result(result)
        self.assertNotIn("trace", payload)
        self.assertNotIn("tool_results", payload)
        self.assertEqual(decode_result(payload, "").answer, "answer")

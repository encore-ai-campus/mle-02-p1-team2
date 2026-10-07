from __future__ import annotations

import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "src" / "shining_chatbot" / "app.py"


class LocalAppSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="shining-chatbot-smoke-")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.environment = patch.dict(os.environ, {
            "SHINING_CHATBOT_DATA_DIR": str(root / "state"),
            "SANUP_P_ROOT": str(root / "empty-sanup"),
            "OPENAI_API_KEY": "",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        os.environ.pop("OPENAI_API_KEY", None)

        from shining_chatbot import chatbot, weather_data

        bridge_call_patch = patch.object(chatbot, "ask_sanup", wraps=chatbot.ask_sanup)
        self.bridge_call = bridge_call_patch.start()
        self.addCleanup(bridge_call_patch.stop)
        bridge_process_patch = patch.object(
            chatbot.subprocess, "run", side_effect=AssertionError("SANUP bridge process must not launch")
        )
        self.bridge_process = bridge_process_patch.start()
        self.addCleanup(bridge_process_patch.stop)

        self.network_spies = [
            patch.object(socket.socket, "connect", side_effect=AssertionError("network access is blocked in smoke tests")),
            patch.object(socket, "create_connection", side_effect=AssertionError("network access is blocked in smoke tests")),
            patch.object(weather_data, "urlopen", side_effect=AssertionError("weather network access is blocked")),
        ]
        self.network_mocks = []
        for spy_patch in self.network_spies:
            self.network_mocks.append(spy_patch.start())
            self.addCleanup(spy_patch.stop)

    def _run_app(self, prompt: str | None = None) -> AppTest:
        app = AppTest.from_file(str(APP_PATH))
        app.query_params["page"] = "chat"
        if prompt is not None:
            app.run(timeout=45)
            self.assertFalse(app.exception, [str(item.message) for item in app.exception])
            self.assertEqual(len(app.chat_input), 1)
            app.chat_input[0].set_value(prompt)
        app.run(timeout=45)
        self.assertFalse(app.exception, [str(item.message) for item in app.exception])
        self._assert_no_external_calls()
        return app

    def _assert_no_external_calls(self) -> None:
        self.bridge_call.assert_not_called()
        self.bridge_process.assert_not_called()
        for spy in self.network_mocks:
            spy.assert_not_called()

    def test_missing_setup_panel_renders_with_relative_file_list(self) -> None:
        app = self._run_app()
        self.assertTrue(any("현장 작업·조치·TBM 질문과 CSV 조회는 사용할 수 있습니다" in item.value for item in app.info))
        self.assertTrue(any("SANUP-P 연결 설정" in item.label for item in app.expander))
        self.assertTrue(any("src/retriever.py" in item.value for item in app.code))
        self.assertTrue(any("chroma_db/personal/chroma.sqlite3" in item.value for item in app.code))

    def test_local_csv_question_returns_sample_grounded_answer(self) -> None:
        app = self._run_app("서울 지역 사고 건수")
        answers = [item.value for item in app.markdown]
        answer = next((value for value in answers if "서울 지역 사고 기록" in value), "")
        self.assertIn("가상 샘플 데이터", answer)
        self.assertIn("서울 지역 사고 기록 18건", answer)
        self._assert_no_external_calls()

    def test_generic_document_question_reports_missing_runtime_without_bridge(self) -> None:
        app = self._run_app("이동식 사다리 안전수칙을 알려줘")
        answers = [item.value for item in app.markdown]
        self.assertTrue(any("SANUP-P 문서 색인에 연결할 수 없습니다" in answer for answer in answers), answers)
        self.bridge_call.assert_not_called()
        self.bridge_process.assert_not_called()
        for spy in self.network_mocks:
            spy.assert_not_called()


if __name__ == "__main__":
    unittest.main()

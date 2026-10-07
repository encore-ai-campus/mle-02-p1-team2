from __future__ import annotations

import ast
import unittest
from pathlib import Path

from shining_chatbot.setup_notice import missing_setup_notice


class MissingSetupNoticeTests(unittest.TestCase):
    def test_notice_includes_setup_and_relative_missing_paths(self) -> None:
        notice = missing_setup_notice(
            Path("/opt/SANUP-P"),
            ["src/retriever.py", "chroma_db/personal/chroma.sqlite3"],
        )
        self.assertIn("SANUP_P_ROOT", notice)
        self.assertIn("export SANUP_P_ROOT=/path/to/SANUP-P", notice)
        self.assertIn(chr(36) + "env:SANUP_P_ROOT", notice)
        self.assertIn("현재 SANUP_P_ROOT: /opt/SANUP-P", notice)
        self.assertIn("- src/retriever.py", notice)
        self.assertIn("- chroma_db/personal/chroma.sqlite3", notice)


class ChatbotGuardOrderTests(unittest.TestCase):
    def test_local_answers_are_checked_before_rag_readiness_guard(self) -> None:
        source = Path(__file__).resolve().parents[1] / "chatbot.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        show_chatbot = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "show_chatbot"
        )
        local_guard = next(
            node for node in ast.walk(show_chatbot)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.UnaryOp)
            and isinstance(node.test.op, ast.Not)
            and isinstance(node.test.operand, ast.Name)
            and node.test.operand.id == "ready"
        )
        calls = [
            node for node in ast.walk(show_chatbot)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        field_call = next(node for node in calls if node.func.id == "field_quick_answer")
        data_call = next(node for node in calls if node.func.id == "answer_data_question")
        rag_call = next(node for node in calls if node.func.id == "ask_sanup")
        self.assertLess(field_call.lineno, local_guard.lineno)
        self.assertLess(data_call.lineno, local_guard.lineno)
        self.assertGreater(rag_call.lineno, local_guard.lineno)

    def test_incomplete_setup_ui_uses_expander_and_notice(self) -> None:
        source = Path(__file__).resolve().parents[1] / "chatbot.py"
        content = source.read_text(encoding="utf-8")
        tree = ast.parse(content)
        self.assertTrue(tree.body)
        self.assertIn("missing_setup_notice", content)
        self.assertIn("with st.expander", content)


if __name__ == "__main__":
    unittest.main()

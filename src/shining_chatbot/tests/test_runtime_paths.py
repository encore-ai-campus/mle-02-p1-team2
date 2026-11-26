from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from shining_chatbot.runtime_paths import (
    DEFAULT_SANUP_P_ROOT,
    missing_sanup_files,
    required_sanup_paths,
    resolve_sanup_root,
    sanup_bridge_command,
    sanup_python_path,
)


class RuntimePathsTests(unittest.TestCase):
    def test_default_root_preserves_windows_compatibility(self) -> None:
        self.assertEqual(resolve_sanup_root({}), DEFAULT_SANUP_P_ROOT)

    def test_environment_root_is_expanded(self) -> None:
        self.assertEqual(resolve_sanup_root({"SANUP_P_ROOT": "~/SANUP-P"}), Path.home() / "SANUP-P")

    def test_blank_environment_root_uses_default(self) -> None:
        self.assertEqual(resolve_sanup_root({"SANUP_P_ROOT": "  "}), DEFAULT_SANUP_P_ROOT)

    def test_platform_interpreter_layouts(self) -> None:
        root = Path("/external/SANUP-P")
        self.assertEqual(
            sanup_python_path(root, windows=True),
            root / ".venv" / "Scripts" / "python.exe",
        )
        self.assertEqual(
            sanup_python_path(root, windows=False),
            root / ".venv" / "bin" / "python",
        )

    def test_missing_file_check_and_bridge_command_share_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            required = required_sanup_paths(root, windows=False)
            for path in required[1:]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()

            interpreter = root / ".venv" / "bin" / "python"
            self.assertEqual(missing_sanup_files(root, windows=False), [".venv/bin/python"])
            command = sanup_bridge_command(root, root / "bridge.py", windows=False)
            self.assertEqual(command[0], str(interpreter))
            self.assertEqual(Path(command[0]), required[0])

            interpreter.parent.mkdir(parents=True, exist_ok=True)
            interpreter.touch()
            self.assertEqual(missing_sanup_files(root, windows=False), [])

    def test_windows_missing_file_check_and_command_share_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            required = required_sanup_paths(root, windows=True)
            for path in required[1:]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()

            self.assertEqual(
                missing_sanup_files(root, windows=True),
                [".venv/Scripts/python.exe"],
            )
            command = sanup_bridge_command(root, root / "bridge.py", windows=True)
            self.assertEqual(Path(command[0]), required[0])

    def test_app_wrappers_use_shared_path_helpers(self) -> None:
        package = Path(__file__).resolve().parents[1]
        for filename, function_name, expected_call in (
            ("chatbot.py", "_root", "resolve_sanup_root"),
            ("chatbot.py", "_missing_files", "missing_sanup_files"),
            ("chatbot.py", "ask_sanup", "sanup_bridge_command"),
            ("case_summary.py", "_root", "resolve_sanup_root"),
        ):
            tree = ast.parse((package / filename).read_text(encoding="utf-8"))
            function = next(
                node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == function_name
            )
            calls = {
                node.func.id
                for node in ast.walk(function)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            self.assertIn(expected_call, calls, f"{filename}:{function_name} must call {expected_call}")


if __name__ == "__main__":
    unittest.main()

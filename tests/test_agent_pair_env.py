import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.agent_pair import codex_environment, run_codex


class CodexEnvironmentTests(unittest.TestCase):
    def test_removes_credentials_and_keeps_cli_configuration(self):
        environment = {
            "OPENAI_API_KEY": "openai-secret",
            "GITHUB_TOKEN": "github-secret",
            "DATABASE_PASSWORD": "db-secret",
            "AWS_ACCESS_KEY_ID": "aws-key",
            "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
            "PATH": "/usr/bin",
            "HOME": "/home/tester",
            "CODEX_HOME": "/home/tester/.codex",
            "OPENAI_MODEL": "gpt-6-luna",
            "CODEX_CLI": "codex",
        }

        result = codex_environment(environment)

        self.assertEqual(result, {
            "PATH": "/usr/bin",
            "HOME": "/home/tester",
            "CODEX_HOME": "/home/tester/.codex",
            "OPENAI_MODEL": "gpt-6-luna",
            "CODEX_CLI": "codex",
        })

    def test_run_codex_passes_filtered_environment_to_subprocess(self):
        environment = {
            "OPENAI_API_KEY": "openai-secret",
            "PATH": "/usr/bin",
            "HOME": "/home/tester",
            "CODEX_HOME": "/home/tester/.codex",
        }
        completed = subprocess.CompletedProcess(
            args=["codex"], returncode=0, stdout="done", stderr="",
        )
        with tempfile.TemporaryDirectory() as directory:
            artifacts = Path(directory)
            with (
                patch.dict(os.environ, environment, clear=True),
                patch("scripts.agent_pair.subprocess.run", return_value=completed) as mocked_run,
            ):
                run_codex(["codex"], artifacts, "implement", 30, artifacts, "test")

        passed_environment = mocked_run.call_args.kwargs["env"]
        self.assertNotIn("OPENAI_API_KEY", passed_environment)
        self.assertEqual(passed_environment["PATH"], "/usr/bin")
        self.assertEqual(passed_environment["HOME"], "/home/tester")
        self.assertEqual(passed_environment["CODEX_HOME"], "/home/tester/.codex")


if __name__ == "__main__":
    unittest.main()

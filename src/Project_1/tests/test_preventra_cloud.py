"""Cloud boundaries: missing configuration never enables a local fallback."""
import unittest
from unittest.mock import patch

from preventra_runtime import CloudConfigurationError, load_cloud_statistics, require_database, validate_database_url
from preventra_agent.observability import get_tracing_client


class CloudTests(unittest.TestCase):
    def test_same_project_direct_and_session_pooler(self):
        for url in ("postgresql://postgres:placeholder@db.project.supabase.co:5432/postgres",
                    "postgresql://postgres.project:placeholder@aws-0-region.pooler.supabase.com:5432/postgres"):
            validate_database_url(url, "https://project.supabase.co")

    def test_local_wrong_project_and_transaction_pooler_rejected(self):
        for url in ("postgresql://postgres:placeholder@localhost:5432/postgres",
                    "postgresql://postgres:placeholder@db.other.supabase.co/postgres",
                    "postgresql://postgres.other:placeholder@aws-0-region.pooler.supabase.com/postgres",
                    "postgresql://postgres.project:placeholder@aws-0-region.pooler.supabase.com:6543/postgres"):
            with self.subTest(url=url), self.assertRaises(CloudConfigurationError) as error:
                validate_database_url(url, "https://project.supabase.co")
            self.assertNotIn("placeholder", str(error.exception))

    def test_database_missing_does_not_use_legacy_default(self):
        with patch("services.safety_rag.DATABASE_URL_CONFIGURED", False):
            with self.assertRaises(CloudConfigurationError):
                require_database()

    def test_statistics_missing_secrets_never_loads_local_files(self):
        with patch("services.safety_rag.setting", return_value=None), \
             patch("services.statistics.load_statistics") as loader:
            with self.assertRaises(CloudConfigurationError):
                load_cloud_statistics()
            loader.assert_not_called()

    def test_cloud_secrets_take_precedence(self):
        from services.safety_rag import setting
        with patch("services.safety_rag.st.secrets", {"OPENAI_API_KEY": "cloud-placeholder"}), \
             patch.dict("os.environ", {"OPENAI_API_KEY": "env-placeholder"}):
            self.assertEqual(setting("OPENAI_API_KEY"), "cloud-placeholder")

    def test_invalid_langfuse_endpoint_only_disables_tracing(self):
        for endpoint in ("http://localhost:3000", "https://unrelated.example", "https://cloud.langfuse.com@unrelated.example"):
            with patch("preventra_agent.observability.tracing_settings", return_value=("public", "secret", endpoint, True)), \
                 patch("preventra_agent.observability._client") as factory:
                self.assertIsNone(get_tracing_client())
                factory.assert_not_called()

    def test_langfuse_initialization_failure_is_optional(self):
        with patch("preventra_agent.observability.tracing_settings", return_value=("public", "secret", "https://cloud.langfuse.com", True)), \
             patch("preventra_agent.observability._client", side_effect=RuntimeError("failure")):
            self.assertIsNone(get_tracing_client())

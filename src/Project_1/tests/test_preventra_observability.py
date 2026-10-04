"""Actual v4 SDK/CallbackHandler with a local exporter; no external requests."""
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool
from langfuse import Langfuse
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import BaseModel

from preventra_agent.models import AgentResult
from preventra_agent.observability import agent_trace, export_mask, get_tracing_client, redact


class QueryInput(BaseModel):
    query: str


class LocalChat(BaseChatModel):
    @property
    def _llm_type(self):
        return "offline-test"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        message = AIMessage(content="테스트 최종 답변", usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})
        return ChatResult(generations=[ChatGeneration(message=message)])


class ObservabilityTests(unittest.TestCase):
    def test_absent_keys_do_not_construct_sdk(self):
        with patch("preventra_agent.observability.tracing_settings", return_value=(None, None, "https://cloud.langfuse.com", True)), \
             patch("preventra_agent.observability._client") as factory:
            self.assertIsNone(get_tracing_client())
            with agent_trace("안녕", "test", "session") as trace:
                self.assertIsNone(trace.config)
                trace.finish(AgentResult("안녕하세요"))
            factory.assert_not_called()

    def test_export_masks_secret_and_personal_fields(self):
        payload = {"password": "hidden", "api_key": "hidden", "question": "문의 test@example.com 010-1234-5678 900101-1234567", "data": "postgresql://user:password@localhost/db"}
        clean = redact(payload)
        self.assertEqual(clean["password"], "[REDACTED]")
        for forbidden in ("test@example.com", "010-1234", "900101", "postgresql://", "hidden"):
            self.assertNotIn(forbidden, json.dumps(clean))

    def test_one_agent_trace_nested_tools_usage_and_session(self):
        exporter = InMemorySpanExporter()
        public = "pk-lf-offline-" + uuid4().hex
        client = Langfuse(public_key=public, secret_key="sk-lf-offline-placeholder",
                          base_url="http://127.0.0.1:1", span_exporter=exporter,
                          mask_otel_spans=export_mask(("private-value-xyz",)))
        conversation = str(uuid4())
        with patch("preventra_agent.observability.get_tracing_client", return_value=client), \
             patch("preventra_agent.observability.tracing_settings", return_value=(public, "unused", "unused", True)):
            for number in range(2):
                with agent_trace("지게차 점검 test@example.com", str(uuid4()), conversation) as trace:
                    LocalChat().invoke("지게차", config=trace.config)
                    for name in ("search_sif_cases", "search_kosha_guides", "get_accident_statistics"):
                        tool = StructuredTool.from_function(lambda query: {"query": query, "secret": "private-value-xyz"}, name=name, description="test", args_schema=QueryInput)
                        tool.invoke({"query": "지게차"}, config=trace.config)
                    trace.finish(AgentResult("답변 test@example.com private-value-xyz"))
        client.flush()
        spans = exporter.get_finished_spans()
        self.assertEqual(len({s.context.trace_id for s in spans}), 2)
        roots = [s for s in spans if s.name == "Preventra Safety Agent"]
        self.assertEqual(len(roots), 2)
        exported_ids = {s.context.span_id for s in spans}
        self.assertTrue(all(s.parent is None or s.parent.span_id not in exported_ids for s in roots))
        for root in roots:
            children = [s for s in spans if s.context.trace_id == root.context.trace_id and s is not root]
            self.assertEqual(len(children), 4)
            self.assertTrue(all(s.parent.span_id == root.context.span_id for s in children))
            self.assertTrue(all(s.attributes.get("session.id") == conversation for s in [root, *children]))
        exported = json.dumps([dict(s.attributes) for s in spans], ensure_ascii=False)
        self.assertNotIn("test@example.com", exported)
        self.assertNotIn("private-value-xyz", exported)
        self.assertIn("langfuse.observation.usage_details", exported)
        self.assertIn("safety-agent", exported)
        self.assertIn("get_accident_statistics", {s.name for s in spans})
        self.assertTrue(all(s.end_time >= s.start_time for s in spans))

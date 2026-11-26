"""Optional Langfuse v4 tracing. No SDK/network initialization without keys."""
from contextlib import ExitStack, contextmanager
from functools import lru_cache
import json
import logging
import re
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)
REDACTED = "[REDACTED]"
SENSITIVE_KEY = re.compile(r"(?i)(password|passwd|secret|api[_-]?key|authorization|credential|(?:database|db)[_-]?url|connection[_-]?string|access[_-]?token|refresh[_-]?token|email|phone|address|full[_-]?name|person[_-]?name)")
PATTERNS = (
    re.compile(r"(?i)(?:postgres(?:ql)?|mysql|mongodb)://[^\s\"'<>]+"),
    re.compile(r"(?i)\b(?:sk|pk)-(?:proj-|lf-)?[A-Za-z0-9_-]{8,}"),
    re.compile(r"\bsb_secret_[A-Za-z0-9_-]+"),
    re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?<!\d)(?:\+82[- .]?)?0\d{1,2}[- .]?\d{3,4}[- .]?\d{4}(?!\d)"),
    re.compile(r"(?<!\d)\d{6}[- ]?[1-8]\d{6}(?!\d)"),
    re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
    re.compile(r"(?i)(?:password|api[_ -]?key|secret|token|비밀번호|성명|이름|연락처|주소)\s*[:=]\s*[^,;\n]+"),
    re.compile(r"[가-힣]{2,4}\s*(?:씨|님|대리|과장|부장|차장)(?=[\s,.:은는이가을를]|$)"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
)


def redact(value, secrets=()):
    if isinstance(value, dict):
        return {key: REDACTED if SENSITIVE_KEY.search(str(key)) else redact(item, secrets)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets) for item in value]
    if not isinstance(value, str):
        return value
    for secret in secrets:
        if secret and len(secret) >= 4:
            value = value.replace(secret, REDACTED)
    if value.lstrip().startswith(("{", "[")):
        try:
            return json.dumps(redact(json.loads(value), secrets), ensure_ascii=False)
        except (ValueError, TypeError):
            pass
    for pattern in PATTERNS:
        value = pattern.sub(REDACTED, value)
    return value


def export_mask(secrets=()):
    def mask(*, params):
        from langfuse.types import MaskOtelSpansResult, OtelSpanPatch
        patches = {}
        for identifier, span in params.spans.items():
            replacements = {}
            for key, value in span.attributes.items():
                cleaned = REDACTED if SENSITIVE_KEY.search(key) else redact(value, secrets)
                if cleaned != value:
                    replacements[key] = cleaned
            # Do not export raw provider exception details as status metadata.
            if "langfuse.observation.status_message" in span.attributes:
                replacements["langfuse.observation.status_message"] = "Execution error; details withheld"
            if replacements:
                patches[identifier] = OtelSpanPatch(set_attributes=replacements)
        return MaskOtelSpansResult(span_patches=patches)
    return mask


def tracing_settings():
    from preventra_settings import setting
    return (setting("LANGFUSE_PUBLIC_KEY"), setting("LANGFUSE_SECRET_KEY"),
            setting("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com",
            (setting("LANGFUSE_TRACING_ENABLED") or "true").lower() != "false")


@lru_cache(maxsize=4)
def _client(public_key, secret_key, base_url):
    from langfuse import Langfuse
    from preventra_settings import secret_values
    secrets = secret_values()
    return Langfuse(public_key=public_key, secret_key=secret_key, base_url=base_url,
                    timeout=5, mask_otel_spans=export_mask(secrets))


def get_tracing_client():
    try:
        public, secret, url, enabled = tracing_settings()
        if not public or not secret or not enabled:
            return None
        endpoint = urlsplit(url)
        if (endpoint.scheme != "https" or endpoint.hostname not in
                {"cloud.langfuse.com", "us.cloud.langfuse.com", "jp.cloud.langfuse.com", "hipaa.cloud.langfuse.com"}
                or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment
                or endpoint.path not in ("", "/") or endpoint.port not in (None, 443)):
            logger.warning("Preventra tracing requires a valid Langfuse Cloud endpoint")
            return None
        return _client(public, secret, url)
    except Exception:
        logger.warning("Preventra tracing unavailable; continuing without tracing")
        return None


class AgentObservation:
    def __init__(self, root=None, callbacks=None):
        self.root = root
        self.config = {"callbacks": callbacks} if callbacks else None

    def finish(self, result):
        if self.root is not None:
            try:
                self.root.update(output={"final_answer": result.final_answer,
                                         "used_tools": result.used_tools, "status": result.status},
                                 level="ERROR" if result.status == "error" else "DEFAULT")
            except Exception:
                logger.warning("Preventra trace update unavailable")


@contextmanager
def agent_trace(question, request_id, conversation_id):
    client = get_tracing_client()
    stack = ExitStack()
    observation = AgentObservation()
    if client is not None:
        try:
            from langfuse import propagate_attributes
            from langfuse.langchain import CallbackHandler
            from langchain_core.messages import ToolMessage

            class SafeHandler(CallbackHandler):
                def on_tool_end(self, output, **kwargs):
                    # Plotly/artifact objects are for UI persistence, not telemetry.
                    if isinstance(output, ToolMessage):
                        output = output.content
                    return super().on_tool_end(output, **kwargs)

            root = stack.enter_context(client.start_as_current_observation(
                name="Preventra Safety Agent", as_type="agent",
                trace_context={"trace_id": client.create_trace_id(seed=request_id)} if request_id else None,
                input={"question": question}))
            stack.enter_context(propagate_attributes(session_id=conversation_id or None,
                tags=["preventra", "safety-agent"],
                metadata={"request_id": request_id, "conversation_id": conversation_id or ""}))
            observation = AgentObservation(root, [SafeHandler(public_key=tracing_settings()[0])])
        except Exception:
            try:
                stack.close()
            except Exception:
                pass
            stack = ExitStack()
            logger.warning("Preventra tracing setup unavailable; continuing")
    try:
        yield observation
    finally:
        # Never pass raw exception objects into automatic span exception recording.
        try:
            stack.close()
        except Exception:
            logger.warning("Preventra tracing export unavailable")

"""Preventra metadata and existing LangChain PostgreSQL message storage."""
from dataclasses import asdict, dataclass
from functools import lru_cache
import re
from uuid import UUID, uuid4

import plotly.io as pio
import psycopg
from langchain_core.messages import AIMessage, HumanMessage
from langchain_postgres import PostgresChatMessageHistory

from preventra_ui.gateway import AssistantRequest, AssistantResult, Evidence


class HistoryUnavailable(RuntimeError):
    pass


def title_from_question(question):
    text = re.sub(r"\s+", " ", question).strip()
    return text if len(text) <= 32 else text[:31].rstrip() + "…"


def encode_result(result):
    # Persist displayed evidence, not unused candidates or debug traces.
    return {"version": 1, "status": result.status, "answer": result.answer,
            "cases": [asdict(e) for e in result.cases], "guides": [asdict(e) for e in result.guides],
            "figures": [pio.to_json(f) for f in result.figures],
            "statistics_caption": result.statistics_caption, "used_tools": result.used_tools,
            "plan_sources": [asdict(e) for e in result.plan_sources]}


def decode_result(payload, fallback):
    if not payload or payload.get("version") != 1:
        return AssistantResult(answer=fallback)
    return AssistantResult(status=payload["status"], answer=payload["answer"],
                           cases=[Evidence(**e) for e in payload.get("cases", [])],
                           guides=[Evidence(**e) for e in payload.get("guides", [])],
                           figures=[pio.from_json(f) for f in payload.get("figures", [])],
                           statistics_caption=payload.get("statistics_caption", ""),
                           used_tools=payload.get("used_tools", []),
                           plan_sources=[Evidence(**e) for e in payload.get("plan_sources", [])])


@dataclass(frozen=True)
class Conversation:
    conversation_id: str
    title: str
    created_at: object
    updated_at: object


class ConversationStore:
    def __init__(self, connection_factory, scope="preventra-local"):
        self.connection_factory = connection_factory
        self.scope = scope

    def ensure_schema(self):
        from services.safety_rag import HISTORY_TABLE
        with self.connection_factory() as conn:
            PostgresChatMessageHistory.create_tables(conn, HISTORY_TABLE)
            conn.execute("""CREATE TABLE IF NOT EXISTS preventra_conversations (
                conversation_id UUID PRIMARY KEY, scope TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '새 대화',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
            conn.execute("""CREATE INDEX IF NOT EXISTS preventra_conversations_recent
                ON preventra_conversations(scope, updated_at DESC)""")

    def create(self, conversation_id=None):
        identifier = str(UUID(conversation_id)) if conversation_id else str(uuid4())
        with self.connection_factory() as conn:
            conn.execute("INSERT INTO preventra_conversations(conversation_id, scope) VALUES (%s, %s)", (identifier, self.scope))
        return identifier

    def list_recent(self, limit=50):
        with self.connection_factory() as conn:
            rows = conn.execute("""SELECT conversation_id, title, created_at, updated_at
                FROM preventra_conversations WHERE scope=%s
                ORDER BY updated_at DESC, conversation_id DESC LIMIT %s""", (self.scope, limit)).fetchall()
        return [Conversation(str(row[0]), *row[1:]) for row in rows]

    def _lock(self, conn, conversation_id):
        row = conn.execute("""SELECT title FROM preventra_conversations
            WHERE conversation_id=%s AND scope=%s FOR UPDATE""", (str(UUID(conversation_id)), self.scope)).fetchone()
        if row is None:
            raise HistoryUnavailable("선택한 대화를 찾을 수 없습니다.")

    def load(self, conversation_id, *, touch=False):
        from services.safety_rag import HISTORY_TABLE
        identifier = str(UUID(conversation_id))
        with self.connection_factory() as conn:
            self._lock(conn, identifier)
            messages = PostgresChatMessageHistory(HISTORY_TABLE, identifier, sync_connection=conn).messages
            if touch:
                conn.execute("UPDATE preventra_conversations SET updated_at=clock_timestamp() WHERE conversation_id=%s", (identifier,))
        turns, pending = [], None
        for message in messages:
            if isinstance(message, HumanMessage):
                pending = message
            elif isinstance(message, AIMessage) and pending is not None:
                request_id = pending.additional_kwargs.get("preventra_request_id")
                if request_id and request_id == message.additional_kwargs.get("preventra_request_id"):
                    turns.append({"request": AssistantRequest(request_id, identifier, pending.content,
                                      context=pending.additional_kwargs.get("preventra_context", {})),
                                  "result": decode_result(message.additional_kwargs.get("preventra_result"), message.content)})
                pending = None
        return turns

    def save_turn(self, request, result):
        from services.safety_rag import HISTORY_TABLE
        from psycopg import sql
        identifier = str(UUID(request.session_id))
        with self.connection_factory() as conn:
            self._lock(conn, identifier)
            duplicate = conn.execute(sql.SQL("""SELECT 1 FROM {} WHERE session_id=%s
                AND message->'data'->'additional_kwargs'->>'preventra_request_id'=%s LIMIT 1""").format(sql.Identifier(HISTORY_TABLE)),
                (identifier, request.request_id)).fetchone()
            if duplicate:
                return False
            first = not conn.execute(sql.SQL("SELECT 1 FROM {} WHERE session_id=%s LIMIT 1").format(sql.Identifier(HISTORY_TABLE)), (identifier,)).fetchone()
            conn.execute("""UPDATE preventra_conversations SET updated_at=clock_timestamp(),
                title=CASE WHEN %s THEN %s ELSE title END WHERE conversation_id=%s""",
                (first, title_from_question(request.question), identifier))
            metadata = {"preventra_request_id": request.request_id}
            if request.context:
                metadata["preventra_context"] = request.context
            messages = [HumanMessage(request.question, additional_kwargs=metadata),
                        AIMessage(result.answer, additional_kwargs={**metadata, "preventra_result": encode_result(result)})]
            # One commit by add_messages: metadata + both messages are atomic.
            PostgresChatMessageHistory(HISTORY_TABLE, identifier, sync_connection=conn).add_messages(messages)
        return True


def get_store():
    from services.safety_rag import setting
    from preventra_runtime import require_database
    return _configured_store(require_database(), setting("PREVENTRA_HISTORY_SCOPE") or "preventra-local")


@lru_cache(maxsize=4)
def _configured_store(database_url, scope):
    store = ConversationStore(lambda: psycopg.connect(database_url, connect_timeout=5), scope=scope)
    store.ensure_schema()
    return store

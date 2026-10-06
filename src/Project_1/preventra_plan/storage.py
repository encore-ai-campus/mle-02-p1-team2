"""Conversation-scoped PostgreSQL plans using Preventra's existing connection."""
from dataclasses import dataclass
from functools import lru_cache
from psycopg.types.json import Jsonb
from preventra_plan.domain import validate_snapshot


class PlanConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class SavedPlan:
    revision: int = 0
    snapshot: dict | None = None


class PlanStore:
    def __init__(self, conversations):
        self.conversations = conversations

    def ensure_schema(self):
        with self.conversations.connection_factory() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS preventra_work_plans (
                conversation_id UUID PRIMARY KEY REFERENCES preventra_conversations(conversation_id),
                revision BIGINT NOT NULL CHECK (revision > 0),
                snapshot JSONB,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now())""")

    def load(self, conversation_id):
        with self.conversations.connection_factory() as conn:
            self.conversations._lock(conn, conversation_id)
            row = conn.execute("SELECT revision, snapshot FROM preventra_work_plans WHERE conversation_id=%s",
                               (conversation_id,)).fetchone()
        result = SavedPlan(*row) if row else SavedPlan()
        validate_snapshot(result.snapshot)
        return result

    def save(self, conversation_id, value, expected_revision):
        validate_snapshot(value)
        with self.conversations.connection_factory() as conn:
            self.conversations._lock(conn, conversation_id)
            row = conn.execute("SELECT revision FROM preventra_work_plans WHERE conversation_id=%s",
                               (conversation_id,)).fetchone()
            revision = row[0] if row else 0
            if revision != expected_revision:
                raise PlanConflict("다른 화면에서 계획이 변경되었습니다. 최신 계획을 확인하고 다시 적용해 주세요.")
            revision += 1
            conn.execute("""INSERT INTO preventra_work_plans(conversation_id, revision, snapshot)
                VALUES (%s, %s, %s) ON CONFLICT (conversation_id) DO UPDATE
                SET revision=EXCLUDED.revision, snapshot=EXCLUDED.snapshot, updated_at=clock_timestamp()""",
                (conversation_id, revision, Jsonb(value) if value is not None else None))
        return SavedPlan(revision, value)


def get_plan_store():
    from preventra_ui.history import get_store
    return _configured(get_store())


@lru_cache(maxsize=4)
def _configured(conversations):
    result = PlanStore(conversations)
    result.ensure_schema()
    return result

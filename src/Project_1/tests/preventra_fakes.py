"""In-memory durable-store substitute used only by offline UI checks."""
from datetime import datetime, timezone
from uuid import uuid4

from preventra_ui.history import Conversation, decode_result, encode_result, title_from_question


class MemoryStore:
    def __init__(self):
        self.rows = {}
        self.fail_save = False

    def create(self, conversation_id=None):
        identifier = conversation_id or str(uuid4())
        now = datetime.now(timezone.utc)
        self.rows[identifier] = {"title": "새 대화", "created": now, "updated": now, "turns": []}
        return identifier

    def list_recent(self):
        return [Conversation(identifier, r["title"], r["created"], r["updated"])
                for identifier, r in sorted(self.rows.items(), key=lambda pair: pair[1]["updated"], reverse=True)]

    def load(self, identifier, touch=False):
        row = self.rows[identifier]
        if touch:
            row["updated"] = datetime.now(timezone.utc)
        return [{"request": req, "result": decode_result(payload, "")} for req, payload in row["turns"]]

    def save_turn(self, request, result):
        if self.fail_save:
            raise RuntimeError("private-connection-string")
        row = self.rows[request.session_id]
        if any(req.request_id == request.request_id for req, _ in row["turns"]):
            return False
        if not row["turns"]:
            row["title"] = title_from_question(request.question)
        row["turns"].append((request, encode_result(result)))
        row["updated"] = datetime.now(timezone.utc)
        return True

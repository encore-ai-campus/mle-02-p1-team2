"""Local durable storage for the single-site field dashboard pilot.

This is a single-workspace store. Optimistic revisions prevent two open browser
sessions from silently overwriting each other's operational records.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path


class StorageConflict(RuntimeError):
    """Raised when another browser session saved a newer field snapshot."""


def database_path() -> Path:
    configured = os.environ.get("SHINING_CHATBOT_DATA_DIR")
    if configured:
        return Path(configured).expanduser() / "field_state.sqlite3"
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = Path(local_app_data) / "ShiningChatbot" / "field_state.sqlite3"
    else:
        candidate = Path.home() / ".local" / "share" / "shining-chatbot" / "field_state.sqlite3"
    parent_to_check = candidate.parent if candidate.parent.exists() else candidate.parent.parent
    if parent_to_check.exists() and os.access(parent_to_check, os.W_OK):
        return candidate

    workspace = Path(__file__).resolve().parents[2]
    if os.access(workspace, os.W_OK):
        return workspace / ".runtime" / "field_state.sqlite3"
    return candidate


class FieldStateStore:
    """Persist one validated backup snapshot with SQLite compare-and-swap."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else database_path()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.parent.chmod(0o700)
        except OSError:
            pass
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS field_snapshot ("
            "workspace TEXT PRIMARY KEY, revision INTEGER NOT NULL, "
            "payload BLOB NOT NULL, payload_hash TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
        return connection

    def load(self) -> tuple[bytes | None, int]:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT payload, revision, payload_hash FROM field_snapshot WHERE workspace = ?",
                ("default",),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None, 0
        payload = bytes(row[0])
        if hashlib.sha256(payload).hexdigest() != row[2]:
            raise ValueError("저장된 현장 기록의 무결성 검사를 통과하지 못했습니다.")
        return payload, int(row[1])

    def save(self, payload: bytes, expected_revision: int) -> int:
        if not isinstance(payload, bytes) or not payload:
            raise ValueError("저장할 현장 기록이 비어 있습니다.")
        if len(payload) > 10 * 1024 * 1024:
            raise ValueError("영구 저장 데이터가 10MB를 넘었습니다. 변경 이력을 백업 후 정리하세요.")
        digest = hashlib.sha256(payload).hexdigest()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT revision, payload_hash FROM field_snapshot WHERE workspace = ?",
                ("default",),
            ).fetchone()
            if row is None:
                if expected_revision != 0:
                    raise StorageConflict("저장본이 초기화되었습니다. 최신 저장본을 다시 불러오세요.")
                connection.execute(
                    "INSERT INTO field_snapshot(workspace, revision, payload, payload_hash) VALUES (?, ?, ?, ?)",
                    ("default", 1, payload, digest),
                )
                revision = 1
            elif digest == row[1]:
                revision = int(row[0])
            elif int(row[0]) != expected_revision:
                raise StorageConflict("다른 브라우저 세션에서 현장 기록이 변경되었습니다.")
            else:
                revision = int(row[0]) + 1
                connection.execute(
                    "UPDATE field_snapshot SET revision = ?, payload = ?, payload_hash = ?, "
                    "updated_at = CURRENT_TIMESTAMP WHERE workspace = ?",
                    (revision, payload, digest, "default"),
                )
            connection.execute("COMMIT")
            return revision
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

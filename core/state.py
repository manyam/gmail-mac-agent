import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class StateManager:
    """Manages SQLite cache of processed threads to prevent duplicate briefings."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_threads (
                    thread_id TEXT PRIMARY KEY,
                    history_id TEXT,
                    message_count INTEGER,
                    last_processed_at TEXT
                )
                """
            )
            conn.commit()

    def is_processed(self, thread_id: str, history_id: str, message_count: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT history_id, message_count FROM processed_threads
                WHERE thread_id = ?
                """,
                (thread_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False
            saved_history_id, saved_count = row
            # If message count or history ID has changed, new messages have arrived in the thread
            if saved_history_id == history_id and saved_count == message_count:
                return True
            return False

    def mark_processed(self, thread_id: str, history_id: str, message_count: int) -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO processed_threads (thread_id, history_id, message_count, last_processed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    history_id = excluded.history_id,
                    message_count = excluded.message_count,
                    last_processed_at = excluded.last_processed_at
                """,
                (thread_id, history_id, message_count, now),
            )
            conn.commit()

    def filter_unseen_threads(
        self, threads_meta: List[Dict[str, Any]], force: bool = False
    ) -> List[Dict[str, Any]]:
        """Filters out threads that were already digested without new messages."""
        if force:
            return threads_meta

        unseen = []
        for t in threads_meta:
            thread_id = t.get("id")
            history_id = t.get("historyId", "")
            # list API doesn't always provide message count directly, so check thread_id + historyId
            if not self.is_processed(thread_id, history_id, 0):
                unseen.append(t)
        return unseen

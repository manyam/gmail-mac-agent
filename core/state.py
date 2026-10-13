import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class StateManager:
    """Manages SQLite cache of processed threads to prevent duplicate briefings."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(processed_threads)")
            columns = [col[1] for col in cursor.fetchall()]
            if not columns:
                cursor.execute(
                    """
                    CREATE TABLE processed_threads (
                        thread_id TEXT,
                        label TEXT DEFAULT '',
                        history_id TEXT,
                        message_count INTEGER,
                        last_processed_at TEXT,
                        PRIMARY KEY (thread_id, label)
                    )
                    """
                )
            elif "label" not in columns:
                # Migrate legacy table with single PRIMARY KEY (thread_id) to composite key
                cursor.execute(
                    """
                    CREATE TABLE processed_threads_new (
                        thread_id TEXT,
                        label TEXT DEFAULT '',
                        history_id TEXT,
                        message_count INTEGER,
                        last_processed_at TEXT,
                        PRIMARY KEY (thread_id, label)
                    )
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO processed_threads_new (thread_id, label, history_id, message_count, last_processed_at)
                    SELECT thread_id, '', history_id, message_count, last_processed_at
                    FROM processed_threads
                    """
                )
                cursor.execute("DROP TABLE processed_threads")
                cursor.execute("ALTER TABLE processed_threads_new RENAME TO processed_threads")
            conn.commit()

    def is_processed(
        self, thread_id: str, history_id: str, message_count: int, label: Optional[str] = None
    ) -> bool:
        lbl = label or ""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT history_id, message_count FROM processed_threads
                WHERE thread_id = ? AND label = ?
                """,
                (thread_id, lbl),
            )
            row = cursor.fetchone()
            if not row:
                return False
            saved_history_id, saved_count = row
            # If message_count is not provided (0), check whether history_id matches
            if message_count == 0:
                return saved_history_id == history_id
            # If message count or history ID has changed, new messages have arrived in the thread
            if saved_history_id == history_id and saved_count == message_count:
                return True
            return False

    def mark_processed(
        self, thread_id: str, history_id: str, message_count: int, label: Optional[str] = None
    ) -> None:
        lbl = label or ""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO processed_threads (thread_id, label, history_id, message_count, last_processed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(thread_id, label) DO UPDATE SET
                    history_id = excluded.history_id,
                    message_count = excluded.message_count,
                    last_processed_at = excluded.last_processed_at
                """,
                (thread_id, lbl, history_id, message_count, now),
            )
            conn.commit()

    def filter_unseen_threads(
        self, threads_meta: List[Dict[str, Any]], force: bool = False, label: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Filters out threads that were already digested without new messages."""
        if force:
            return threads_meta

        unseen = []
        for t in threads_meta:
            thread_id = t.get("id")
            history_id = t.get("historyId", "")
            # list API doesn't always provide message count directly, so check thread_id + historyId
            if not self.is_processed(thread_id, history_id, 0, label=label):
                unseen.append(t)
        return unseen

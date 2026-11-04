import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "atlas_logs.db"

class DatabaseManager:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def init_db(self):
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    command TEXT NOT NULL,
                    speaker_verified INTEGER DEFAULT 0,
                    confidence REAL DEFAULT 0.0,
                    route TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response TEXT,
                    latency_ms INTEGER DEFAULT 0
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON action_logs(timestamp)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telegram_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    update_id INTEGER UNIQUE,
                    chat_id TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    command_text TEXT NOT NULL,
                    image_path TEXT,
                    source TEXT DEFAULT 'telegram',
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    executed_at TEXT,
                    response TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tg_queue_status ON telegram_queue(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tg_update_id ON telegram_queue(update_id)")
            conn.commit()

    def log_action(
        self,
        source: str,
        command: str,
        route: str,
        status: str,
        response: Optional[str] = None,
        speaker_verified: bool = False,
        confidence: float = 0.0,
        latency_ms: int = 0
    ) -> int:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO action_logs (
                    timestamp, source, command, speaker_verified,
                    confidence, route, status, response, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now, source, command, 1 if speaker_verified else 0,
                confidence, route, status, response or "", latency_ms
            ))
            conn.commit()
            return cursor.lastrowid

    def get_logs(self, limit: int = 50, offset: int = 0, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM action_logs"
            params = []
            if status_filter:
                query += " WHERE status = ?"
                params.append(status_filter)
            query += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def clear_logs(self) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM action_logs")
            conn.commit()
            return True

    def is_telegram_update_processed(self, update_id: Optional[int]) -> bool:
        if update_id is None:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM telegram_queue WHERE update_id = ? AND status != 'pending' LIMIT 1", (update_id,))
            return cursor.fetchone() is not None

    def enqueue_telegram_message(
        self,
        chat_id: str,
        message_id: int,
        command_text: str,
        update_id: Optional[int] = None,
        image_path: Optional[str] = None,
        status: str = "pending",
        response: Optional[str] = None
    ) -> Optional[int]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if update_id is not None:
                cursor.execute("SELECT id, status FROM telegram_queue WHERE update_id = ? LIMIT 1", (update_id,))
                row = cursor.fetchone()
                if row:
                    return None  # already enqueued or processed
            cursor.execute("""
                INSERT INTO telegram_queue (
                    update_id, chat_id, message_id, command_text,
                    image_path, source, status, created_at, response
                ) VALUES (?, ?, ?, ?, ?, 'telegram', ?, ?, ?)
            """, (
                update_id, str(chat_id), message_id, command_text,
                image_path, status, now, response
            ))
            conn.commit()
            return cursor.lastrowid

    def get_next_pending_telegram_message(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM telegram_queue
                WHERE status = 'pending'
                ORDER BY id ASC
                LIMIT 1
            """)
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_telegram_message_status(self, queue_id: int, status: str, response: Optional[str] = None):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status in ("completed", "failed"):
                cursor.execute("""
                    UPDATE telegram_queue
                    SET status = ?, response = ?, executed_at = ?
                    WHERE id = ?
                """, (status, response or "", now, queue_id))
            else:
                cursor.execute("""
                    UPDATE telegram_queue
                    SET status = ?
                    WHERE id = ?
                """, (status, queue_id))
            conn.commit()

    def get_pending_telegram_queue_count(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM telegram_queue WHERE status = 'pending'")
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def get_telegram_queue(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM telegram_queue ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

db_manager = DatabaseManager()

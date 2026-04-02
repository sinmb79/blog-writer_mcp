"""
bots/prompt_layer/prompt_tracker.py
SQLite-based prompt logging infrastructure.

V3.0: Log every prompt to SQLite. No auto-improvement yet.
V3.1: Analyze logs → extract patterns → auto-improve.

Schema:
  prompt_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    category      TEXT NOT NULL,    -- 'video' | 'search' | 'tts' | 'writing' | ...
    engine        TEXT NOT NULL,    -- target engine name
    prompt        TEXT NOT NULL,    -- full prompt text
    result_quality REAL DEFAULT -1, -- 0.0-1.0, -1 = not evaluated
    user_edited   INTEGER DEFAULT 0, -- 1 if user manually edited the result
    created_at    TEXT NOT NULL     -- ISO 8601 timestamp
  )
"""
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH = BASE_DIR / 'data' / 'prompt_log.db'

# DDL for creating the table
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prompt_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    category       TEXT    NOT NULL,
    engine         TEXT    NOT NULL,
    prompt         TEXT    NOT NULL,
    result_quality REAL    NOT NULL DEFAULT -1,
    user_edited    INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_category ON prompt_log (category);
CREATE INDEX IF NOT EXISTS idx_engine   ON prompt_log (engine);
CREATE INDEX IF NOT EXISTS idx_created  ON prompt_log (created_at);
"""


class PromptTracker:
    """
    Logs prompts to SQLite for future analysis and auto-improvement.

    V3.0: Logging only.
    V3.1: Will add get_engine_preferences() and suggest_improvement().

    Usage:
        tracker = PromptTracker()
        tracker.log('video', 'kling_free', prompt_text)
        tracker.log('search', 'pexels', query_text, result_quality=0.8)
    """

    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._initialized = False

    def _ensure_db(self) -> None:
        """Create database and tables if they don't exist."""
        if self._initialized:
            return

        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                for statement in _CREATE_TABLE_SQL.strip().split(';'):
                    stmt = statement.strip()
                    if stmt:
                        conn.execute(stmt)
                conn.commit()
            self._initialized = True
            logger.debug(f'[트래커] DB 초기화: {self._db_path}')
        except sqlite3.Error as e:
            logger.error(f'[트래커] DB 초기화 실패: {e}')

    def log(
        self,
        category: str,
        engine: str,
        prompt: str,
        result_quality: float = -1.0,
        user_edited: bool = False,
    ) -> Optional[int]:
        """
        Log a prompt to SQLite.

        Args:
            category: Prompt category ('video', 'search', 'tts', 'writing', etc.)
            engine: Target engine name ('kling_free', 'pexels', 'elevenlabs', etc.)
            prompt: Full prompt text
            result_quality: Quality score 0.0-1.0, or -1 if not evaluated
            user_edited: True if user manually modified the AI output

        Returns: Row ID of inserted record, or None on error
        """
        self._ensure_db()

        if not category or not engine or not prompt:
            logger.warning('[트래커] 필수 파라미터 누락 — 로깅 건너뜀')
            return None

        created_at = datetime.now(timezone.utc).isoformat()

        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                cursor = conn.execute(
                    """INSERT INTO prompt_log
                       (category, engine, prompt, result_quality, user_edited, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (category, engine, prompt, float(result_quality), int(user_edited), created_at)
                )
                conn.commit()
                row_id = cursor.lastrowid
                logger.debug(f'[트래커] 로그 저장: id={row_id}, category={category}, engine={engine}')
                return row_id
        except sqlite3.Error as e:
            logger.error(f'[트래커] 로그 저장 실패: {e}')
            return None

    def get_recent(
        self,
        category: Optional[str] = None,
        engine: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Retrieve recent log entries.

        Args:
            category: Filter by category (None = all)
            engine: Filter by engine (None = all)
            limit: Max records to return

        Returns: List of dicts with log fields
        """
        self._ensure_db()

        conditions = []
        params = []

        if category:
            conditions.append('category = ?')
            params.append(category)
        if engine:
            conditions.append('engine = ?')
            params.append(engine)

        where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
        params.append(limit)

        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    f'SELECT * FROM prompt_log {where} ORDER BY created_at DESC LIMIT ?',
                    params
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f'[트래커] 조회 실패: {e}')
            return []

    def get_stats(self) -> dict:
        """
        Return summary statistics.

        Returns: {
            'total': int,
            'by_category': {category: count},
            'by_engine': {engine: count},
            'avg_quality': float,
            'user_edited_count': int,
        }
        """
        self._ensure_db()

        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                total = conn.execute('SELECT COUNT(*) FROM prompt_log').fetchone()[0]

                by_cat = dict(conn.execute(
                    'SELECT category, COUNT(*) FROM prompt_log GROUP BY category'
                ).fetchall())

                by_eng = dict(conn.execute(
                    'SELECT engine, COUNT(*) FROM prompt_log GROUP BY engine'
                ).fetchall())

                avg_q = conn.execute(
                    'SELECT AVG(result_quality) FROM prompt_log WHERE result_quality >= 0'
                ).fetchone()[0]

                edited = conn.execute(
                    'SELECT COUNT(*) FROM prompt_log WHERE user_edited = 1'
                ).fetchone()[0]

                return {
                    'total': total,
                    'by_category': by_cat,
                    'by_engine': by_eng,
                    'avg_quality': round(avg_q, 3) if avg_q is not None else None,
                    'user_edited_count': edited,
                }
        except sqlite3.Error as e:
            logger.error(f'[트래커] 통계 조회 실패: {e}')
            return {}

    # V3.1 stubs (not implemented yet)

    def get_engine_preferences(self, engine: str) -> dict:
        """
        V3.1: Analyze logs to extract what works best for an engine.
        Returns: {} in V3.0 (not implemented)
        """
        logger.debug('[트래커] get_engine_preferences — V3.1에서 구현 예정')
        return {}

    def suggest_improvement(self, category: str, engine: str) -> str:
        """
        V3.1: Suggest prompt improvements based on historical data.
        Returns: '' in V3.0 (not implemented)
        """
        logger.debug('[트래커] suggest_improvement — V3.1에서 구현 예정')
        return ''


# ── Standalone test ──────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    import tempfile

    if '--test' in sys.argv:
        print("=== Prompt Tracker Test ===")

        # Use temp DB for testing
        with tempfile.TemporaryDirectory() as tmp:
            test_db = Path(tmp) / 'test_prompt_log.db'
            tracker = PromptTracker(db_path=test_db)

            # Log some prompts
            id1 = tracker.log('video', 'kling_free', 'A cinematic shot of technology', result_quality=0.8)
            id2 = tracker.log('search', 'pexels', 'artificial intelligence screen', result_quality=0.9)
            id3 = tracker.log('tts', 'edge_tts', 'AI와 ChatGPT가 SEO를 바꾸고 있어요', user_edited=True)
            id4 = tracker.log('video', 'kling_free', 'Korean business meeting professional')

            print(f"Logged 4 entries (IDs: {id1}, {id2}, {id3}, {id4})")

            # Get stats
            stats = tracker.get_stats()
            print(f"Stats: total={stats['total']}, avg_quality={stats['avg_quality']}")
            print(f"By category: {stats['by_category']}")
            print(f"User edited: {stats['user_edited_count']}")

            # Get recent
            recent = tracker.get_recent(category='video', limit=10)
            print(f"Recent video prompts: {len(recent)} entries")

            # Test V3.1 stubs
            prefs = tracker.get_engine_preferences('kling_free')
            print(f"V3.1 stub (engine_preferences): {prefs}")

        print("All tests passed!")

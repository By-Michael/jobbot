"""
database/db.py — Async SQLite database access layer.
All queries use aiosqlite for non-blocking I/O.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite

from config import DATABASE_PATH
from database.models import ALL_TABLES

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Create all tables if they do not exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        for statement in ALL_TABLES:
            await db.execute(statement)
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.commit()
    logger.info("Database initialised.")


# ─── Users ────────────────────────────────────────────────────────────────────

async def upsert_user(user_id: int, username: Optional[str]) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username),
        )
        await db.commit()


# ─── Raw Jobs ─────────────────────────────────────────────────────────────────

async def insert_raw_job(
    channel_name: str,
    channel_id: int,
    message_id: int,
    text: str,
    post_date: Optional[str],
    source_link: Optional[str],
    keyword_used: Optional[str],
) -> Optional[int]:
    """Insert a raw job; returns the new row id or None on duplicate."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO raw_jobs
                    (channel_name, channel_id, message_id, text, post_date, source_link, keyword_used)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (channel_name, channel_id, message_id, text, post_date, source_link, keyword_used),
            )
            await db.commit()
            if cursor.lastrowid and cursor.rowcount:
                return cursor.lastrowid
        except Exception as exc:
            logger.error("insert_raw_job error: %s", exc)
    return None


async def get_unfiltered_raw_jobs() -> list[dict]:
    """Return raw jobs that have not yet been processed by the AI filter."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT r.* FROM raw_jobs r
            LEFT JOIN filtered_jobs f ON f.raw_job_id = r.id
            WHERE f.id IS NULL
            ORDER BY r.id ASC
            """
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ─── Filtered Jobs ────────────────────────────────────────────────────────────

async def insert_filtered_job(
    raw_job_id: int,
    is_valid_job: bool,
    deadline: Optional[str],
    is_expired: bool,
    contact_info: Optional[str],
    validation_notes: Optional[str],
) -> Optional[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO filtered_jobs
                (raw_job_id, is_valid_job, deadline, is_expired, contact_info, validation_notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (raw_job_id, int(is_valid_job), deadline, int(is_expired), contact_info, validation_notes),
        )
        await db.commit()
        return cursor.lastrowid


async def get_valid_unorganized_filtered_jobs() -> list[dict]:
    """Return valid filtered jobs that have not yet been organised."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT f.*, r.text AS raw_text, r.source_link, r.channel_name
            FROM filtered_jobs f
            JOIN raw_jobs r ON r.id = f.raw_job_id
            LEFT JOIN organized_jobs o ON o.filtered_job_id = f.id
            WHERE f.is_valid_job = 1 AND f.is_expired = 0 AND o.id IS NULL
            ORDER BY f.id ASC
            """
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ─── Organized Jobs ───────────────────────────────────────────────────────────

async def insert_organized_job(
    filtered_job_id: int,
    title: str,
    company: Optional[str],
    description: Optional[str],
    location: Optional[str],
    payment: Optional[str],
    deadline: Optional[str],
    contact: Optional[str],
    source: Optional[str],
    source_link: Optional[str],
) -> Optional[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO organized_jobs
                (filtered_job_id, title, company, description, location,
                 payment, deadline, contact, source, source_link)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (filtered_job_id, title, company, description, location,
             payment, deadline, contact, source, source_link),
        )
        await db.commit()
        return cursor.lastrowid


async def search_organized_jobs(keywords: list[str]) -> list[dict]:
    """Search organised jobs by a list of keywords (case-insensitive, any match)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        conditions = " OR ".join(
            ["LOWER(title) LIKE ? OR LOWER(description) LIKE ?"] * len(keywords)
        )
        params = []
        for kw in keywords:
            like = f"%{kw.lower()}%"
            params += [like, like]
        query = f"""
            SELECT * FROM organized_jobs
            WHERE is_expired = 0 AND ({conditions})
            ORDER BY organized_at DESC
        """
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_todays_jobs() -> list[dict]:
    """Return organised jobs from the last 24 hours."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        since = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        cursor = await db.execute(
            "SELECT * FROM organized_jobs WHERE is_expired = 0 AND organized_at >= ? ORDER BY organized_at DESC",
            (since,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_all_active_organized_jobs() -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM organized_jobs WHERE is_expired = 0 ORDER BY organized_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def mark_job_expired(job_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE organized_jobs SET is_expired = 1 WHERE id = ?", (job_id,)
        )
        await db.commit()


# ─── Saved Jobs ───────────────────────────────────────────────────────────────

async def save_job(user_id: int, job_id: int) -> bool:
    """
    Save a job for a user.

    BUG FIX #4: previously always returned True even for duplicates.
    Now checks rowcount to only return True when a row was actually inserted.
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            cursor = await db.execute(
                "INSERT OR IGNORE INTO saved_jobs (user_id, organized_job_id) VALUES (?, ?)",
                (user_id, job_id),
            )
            await db.commit()
            # rowcount == 1 means a new row was inserted; 0 means duplicate (IGNORE'd)
            return cursor.rowcount == 1
        except Exception as exc:
            logger.error("save_job error: %s", exc)
            return False


async def unsave_job(user_id: int, job_id: int) -> None:
    """Remove a saved job for a user (BUG FIX #5 — new function)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM saved_jobs WHERE user_id = ? AND organized_job_id = ?",
            (user_id, job_id),
        )
        await db.commit()


async def get_saved_jobs(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT o.* FROM organized_jobs o
            JOIN saved_jobs s ON s.organized_job_id = o.id
            WHERE s.user_id = ? AND o.is_expired = 0
            ORDER BY s.saved_at DESC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ─── Notifications ────────────────────────────────────────────────────────────

async def add_notification(user_id: int, keyword: str, expanded_keywords: list[str]) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_notifications (user_id, keyword, expanded_keywords)
            VALUES (?, ?, ?)
            """,
            (user_id, keyword, json.dumps(expanded_keywords)),
        )
        await db.commit()


async def get_active_notifications() -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM user_notifications WHERE enabled = 1"
        )
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            row = dict(r)
            row["expanded_keywords"] = json.loads(row["expanded_keywords"])
            result.append(row)
        return result


async def get_user_notifications(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM user_notifications WHERE user_id = ? AND enabled = 1",
            (user_id,),
        )
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            row = dict(r)
            row["expanded_keywords"] = json.loads(row["expanded_keywords"])
            result.append(row)
        return result


async def disable_notification(notification_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE user_notifications SET enabled = 0 WHERE id = ?",
            (notification_id,),
        )
        await db.commit()

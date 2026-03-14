"""
database/models.py — SQLite schema definitions.
"""

CREATE_RAW_JOBS = """
CREATE TABLE IF NOT EXISTS raw_jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_name  TEXT    NOT NULL,
    channel_id    INTEGER NOT NULL,
    message_id    INTEGER NOT NULL,
    text          TEXT    NOT NULL,
    post_date     TEXT,
    source_link   TEXT,
    keyword_used  TEXT,
    scraped_at    TEXT    DEFAULT (datetime('now')),
    UNIQUE(channel_id, message_id)
);
"""

CREATE_FILTERED_JOBS = """
CREATE TABLE IF NOT EXISTS filtered_jobs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_job_id        INTEGER NOT NULL REFERENCES raw_jobs(id),
    is_valid_job      INTEGER NOT NULL DEFAULT 0,
    deadline          TEXT,
    is_expired        INTEGER NOT NULL DEFAULT 0,
    contact_info      TEXT,
    validation_notes  TEXT,
    created_at        TEXT DEFAULT (datetime('now'))
);
"""

CREATE_ORGANIZED_JOBS = """
CREATE TABLE IF NOT EXISTS organized_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filtered_job_id INTEGER NOT NULL REFERENCES filtered_jobs(id),
    title           TEXT,
    company         TEXT,
    description     TEXT,
    location        TEXT,
    payment         TEXT,
    deadline        TEXT,
    contact         TEXT,
    source          TEXT,
    source_link     TEXT,
    is_expired      INTEGER NOT NULL DEFAULT 0,
    organized_at    TEXT DEFAULT (datetime('now'))
);
"""

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_SAVED_JOBS = """
CREATE TABLE IF NOT EXISTS saved_jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(user_id),
    organized_job_id INTEGER NOT NULL REFERENCES organized_jobs(id),
    saved_at         TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, organized_job_id)
);
"""

CREATE_USER_NOTIFICATIONS = """
CREATE TABLE IF NOT EXISTS user_notifications (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL REFERENCES users(user_id),
    keyword           TEXT NOT NULL,
    expanded_keywords TEXT NOT NULL,
    enabled           INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT DEFAULT (datetime('now'))
);
"""

ALL_TABLES = [
    CREATE_RAW_JOBS,
    CREATE_FILTERED_JOBS,
    CREATE_ORGANIZED_JOBS,
    CREATE_USERS,
    CREATE_SAVED_JOBS,
    CREATE_USER_NOTIFICATIONS,
]

from __future__ import annotations

from sqlalchemy import text

from src.core.database import Database

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    subject TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    manager_id INTEGER,
    opened_at TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at TEXT,
    sla_due TEXT
);

CREATE TABLE IF NOT EXISTS ticket_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    sender_role TEXT NOT NULL DEFAULT 'client',
    text TEXT NOT NULL,
    file_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS canned_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    category TEXT DEFAULT 'all',
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS managers (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sla_settings (
    category TEXT PRIMARY KEY,
    reply_minutes INTEGER NOT NULL DEFAULT 30,
    close_hours INTEGER NOT NULL DEFAULT 24
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL UNIQUE,
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    text TEXT,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tickets_status_sla ON tickets(status, sla_due);
CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket ON ticket_messages(ticket_id);
"""


async def migrate(db: Database) -> None:
    async with db.transaction() as conn:
        for statement in SCHEMA.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                await conn.execute(text(stmt))

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from src.core.database import Database


async def create_ticket(
    db: Database,
    *,
    user_id: int,
    category: str,
    subject: str = "",
) -> int:
    async with db.transaction() as session:
        result = await session.execute(
            text(
                "INSERT INTO tickets (user_id, category, subject, status) "
                "VALUES (:uid, :cat, :subj, 'new')"
            ),
            {"uid": user_id, "cat": category, "subj": subject},
        )
        ticket_id = result.lastrowid  # type: ignore[attr-defined]
        assert ticket_id is not None
        await session.execute(
            text(
                "INSERT INTO ticket_messages (ticket_id, sender_id, sender_role, text) "
                "VALUES (:tid, :sid, 'client', :txt)"
            ),
            {"tid": ticket_id, "sid": user_id, "txt": subject},
        )
        return int(ticket_id)


async def get_ticket(db: Database, ticket_id: int) -> dict[str, Any] | None:
    async with db.session() as session:
        result = await session.execute(
            text("SELECT * FROM tickets WHERE id = :id"), {"id": ticket_id}
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None


async def get_user_tickets(db: Database, user_id: int) -> list[dict[str, Any]]:
    async with db.session() as session:
        result = await session.execute(
            text(
                "SELECT * FROM tickets WHERE user_id = :uid ORDER BY opened_at DESC"
            ),
            {"uid": user_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_new_tickets(db: Database) -> list[dict[str, Any]]:
    async with db.session() as session:
        result = await session.execute(
            text("SELECT * FROM tickets WHERE status = 'new' ORDER BY opened_at ASC")
        )
        return [dict(r) for r in result.mappings().all()]


async def take_ticket(db: Database, ticket_id: int, manager_id: int) -> bool:
    async with db.transaction() as session:
        result = await session.execute(
            text(
                "UPDATE tickets SET manager_id = :mid, status = 'taken' "
                "WHERE id = :tid AND status = 'new'"
            ),
            {"mid": manager_id, "tid": ticket_id},
        )
        if result.rowcount == 0:  # type: ignore[attr-defined]
            return False
        await session.execute(
            text(
                "INSERT INTO ticket_messages (ticket_id, sender_id, sender_role, text) "
                "VALUES (:tid, :sid, 'system', 'Тикет взят в работу')"
            ),
            {"tid": ticket_id, "sid": manager_id},
        )
        return True


async def add_message(
    db: Database,
    *,
    ticket_id: int,
    sender_id: int,
    sender_role: str,
    text_content: str,
) -> None:
    async with db.transaction() as session:
        await session.execute(
            text(
                "INSERT INTO ticket_messages (ticket_id, sender_id, sender_role, text) "
                "VALUES (:tid, :sid, :role, :txt)"
            ),
            {"tid": ticket_id, "sid": sender_id, "role": sender_role, "txt": text_content},
        )


async def get_ticket_messages(db: Database, ticket_id: int) -> list[dict[str, Any]]:
    async with db.session() as session:
        result = await session.execute(
            text(
                "SELECT * FROM ticket_messages WHERE ticket_id = :tid ORDER BY created_at ASC"
            ),
            {"tid": ticket_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def close_ticket(db: Database, ticket_id: int) -> None:
    async with db.transaction() as session:
        await session.execute(
            text(
                "UPDATE tickets SET status = 'closed', closed_at = datetime('now') WHERE id = :tid"
            ),
            {"tid": ticket_id},
        )
        await session.execute(
            text(
                "INSERT INTO ticket_messages (ticket_id, sender_id, sender_role, text) "
                "VALUES (:tid, 0, 'system', 'Тикет закрыт')"
            ),
            {"tid": ticket_id},
        )


async def escalate_ticket(db: Database, ticket_id: int) -> None:
    async with db.transaction() as session:
        await session.execute(
            text("UPDATE tickets SET status = 'escalated' WHERE id = :tid"),
            {"tid": ticket_id},
        )


async def add_feedback(
    db: Database, ticket_id: int, rating: int, feedback_text: str
) -> None:
    async with db.transaction() as session:
        await session.execute(
            text("INSERT INTO feedback (ticket_id, rating, text) VALUES (:tid, :r, :t)"),
            {"tid": ticket_id, "r": rating, "t": feedback_text},
        )


async def get_ticket_stats(db: Database, period: str = "day") -> dict[str, int]:
    interval = "1 day" if period == "day" else "7 days"
    async with db.session() as session:
        result = await session.execute(
            text(
                f"SELECT status, COUNT(*) as cnt FROM tickets "
                f"WHERE opened_at >= datetime('now', '-{interval}') GROUP BY status"
            )
        )
        rows = result.mappings().all()
        return {r["status"]: r["cnt"] for r in rows}


async def get_manager_stats(db: Database, manager_id: int) -> dict[str, int]:
    async with db.session() as session:
        result = await session.execute(
            text(
                "SELECT COUNT(*) as cnt FROM tickets "
                "WHERE manager_id = :mid AND status = 'closed'"
            ),
            {"mid": manager_id},
        )
        row = result.fetchone()
        return {"closed": int(row[0]) if row else 0}


async def get_active_managers(db: Database) -> list[dict[str, Any]]:
    async with db.session() as session:
        result = await session.execute(
            text("SELECT * FROM managers WHERE is_active = 1 ORDER BY name")
        )
        return [dict(r) for r in result.mappings().all()]


async def get_overdue_tickets(
    db: Database, sla_minutes: int = 30
) -> list[dict[str, Any]]:
    async with db.session() as session:
        result = await session.execute(
            text(
                "SELECT * FROM tickets "
                "WHERE status IN ('taken', 'in_progress') "
                "AND sla_due IS NOT NULL AND sla_due <= datetime('now')"
            )
        )
        return [dict(r) for r in result.mappings().all()]


async def get_canned_responses(
    db: Database, category: str | None = None
) -> list[dict[str, Any]]:
    async with db.session() as session:
        if category:
            result = await session.execute(
                text(
                    "SELECT * FROM canned_responses "
                    "WHERE is_active = 1 AND (category = :cat OR category = 'all')"
                ),
                {"cat": category},
            )
        else:
            result = await session.execute(
                text("SELECT * FROM canned_responses WHERE is_active = 1")
            )
        return [dict(r) for r in result.mappings().all()]

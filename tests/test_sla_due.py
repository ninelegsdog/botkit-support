"""SLA: sla_due заполняется при создании тикета и переносится на срок
закрытия при ответе менеджера; просроченный тикет виден циклу эскалации."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text

from src.support import service


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _due(ticket: dict) -> datetime:
    assert ticket is not None
    raw = ticket["sla_due"]
    assert raw is not None, "sla_due не заполнен"
    return datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S")


async def test_sla_due_set_on_create(db) -> None:
    tid = await service.create_ticket(
        db, user_id=1, category="bug", subject="x", sla_minutes=30
    )
    ticket = await service.get_ticket(db, tid)
    delta = (_due(ticket) - _utcnow()).total_seconds()
    assert 29 * 60 <= delta <= 31 * 60


async def test_sla_due_moves_to_close_on_manager_reply(db) -> None:
    tid = await service.create_ticket(
        db, user_id=1, category="bug", subject="x", sla_minutes=30
    )
    await service.add_message(
        db,
        ticket_id=tid,
        sender_id=42,
        sender_role="manager",
        text_content="ok",
        sla_close_hours=24,
    )
    ticket = await service.get_ticket(db, tid)
    delta = (_due(ticket) - _utcnow()).total_seconds()
    assert 23.5 * 3600 <= delta <= 24.5 * 3600


async def test_client_message_does_not_touch_sla(db) -> None:
    tid = await service.create_ticket(
        db, user_id=1, category="bug", subject="x", sla_minutes=30
    )
    before = _due(await service.get_ticket(db, tid))
    await service.add_message(
        db, ticket_id=tid, sender_id=1, sender_role="client", text_content="hi"
    )
    after = _due(await service.get_ticket(db, tid))
    assert after == before


async def test_overdue_visible_after_deadline(db) -> None:
    tid = await service.create_ticket(
        db, user_id=1, category="bug", subject="x", sla_minutes=30
    )
    async with db.transaction() as session:
        await session.execute(
            text(
                "UPDATE tickets SET status = 'taken', "
                "sla_due = datetime('now', '-5 minutes') WHERE id = :tid"
            ),
            {"tid": tid},
        )
    overdue = await service.get_overdue_tickets(db)
    assert any(t["id"] == tid for t in overdue)

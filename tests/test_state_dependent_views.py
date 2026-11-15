"""State-dependent view tests for support."""

from __future__ import annotations

import pytest

from src.support import service


@pytest.mark.asyncio
async def test_new_tickets_empty_vs_populated(db):
    assert await service.get_new_tickets(db) == []

    tid = await service.create_ticket(db, user_id=1, category="bug", subject="Help")
    tickets = await service.get_new_tickets(db)
    assert len(tickets) == 1
    assert tickets[0]["id"] == tid


@pytest.mark.asyncio
async def test_ticket_missing_vs_present(db):
    assert await service.get_ticket(db, 99999) is None

    tid = await service.create_ticket(db, user_id=1, category="bug", subject="Help")
    t = await service.get_ticket(db, tid)
    assert t is not None
    assert t["subject"] == "Help"


@pytest.mark.asyncio
async def test_user_tickets_empty_vs_populated(db):
    assert await service.get_user_tickets(db, 1) == []

    await service.create_ticket(db, user_id=1, category="bug", subject="Help")
    tickets = await service.get_user_tickets(db, 1)
    assert len(tickets) == 1


@pytest.mark.asyncio
async def test_ticket_messages_empty_vs_populated(db):
    tid = await service.create_ticket(db, user_id=1, category="bug", subject="Help")
    initial = await service.get_ticket_messages(db, tid)
    assert len(initial) >= 1

    await service.add_message(db, ticket_id=tid, sender_id=1, sender_role="client", text_content="hello")
    msgs = await service.get_ticket_messages(db, tid)
    assert len(msgs) == len(initial) + 1
    assert any(m["text"] == "hello" for m in msgs)


@pytest.mark.asyncio
async def test_close_ticket_changes_state(db):
    tid = await service.create_ticket(db, user_id=1, category="bug", subject="Help")
    ticket = await service.get_ticket(db, tid)
    assert ticket["status"] == "new"

    await service.close_ticket(db, tid, user_id=1)
    ticket = await service.get_ticket(db, tid)
    assert ticket["status"] == "closed"
    assert ticket["closed_at"] is not None

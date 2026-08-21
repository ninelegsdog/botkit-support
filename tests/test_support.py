from __future__ import annotations

import pytest

from src.support import service


@pytest.mark.asyncio
async def test_create_ticket(db):
    ticket_id = await service.create_ticket(
        db, user_id=123, category="payment", subject="Problem"
    )
    assert ticket_id > 0


@pytest.mark.asyncio
async def test_get_ticket(db):
    ticket_id = await service.create_ticket(db, user_id=123, category="payment")
    ticket = await service.get_ticket(db, ticket_id)
    assert ticket is not None
    assert ticket["category"] == "payment"


@pytest.mark.asyncio
async def test_take_ticket(db):
    ticket_id = await service.create_ticket(db, user_id=123, category="payment")
    success = await service.take_ticket(db, ticket_id, 456)
    assert success is True
    ticket = await service.get_ticket(db, ticket_id)
    assert ticket["status"] == "taken"


@pytest.mark.asyncio
async def test_take_ticket_race(db):
    ticket_id = await service.create_ticket(db, user_id=123, category="payment")
    first = await service.take_ticket(db, ticket_id, 456)
    assert first is True
    second = await service.take_ticket(db, ticket_id, 789)
    assert second is False


@pytest.mark.asyncio
async def test_add_message(db):
    ticket_id = await service.create_ticket(db, user_id=123, category="payment")
    await service.add_message(
        db, ticket_id=ticket_id, sender_id=123, sender_role="client", text_content="Hello"
    )
    messages = await service.get_ticket_messages(db, ticket_id)
    assert len(messages) == 2  # system message + client message


@pytest.mark.asyncio
async def test_close_ticket(db):
    ticket_id = await service.create_ticket(db, user_id=123, category="payment")
    await service.take_ticket(db, ticket_id, 456)
    await service.close_ticket(db, ticket_id)
    ticket = await service.get_ticket(db, ticket_id)
    assert ticket["status"] == "closed"


@pytest.mark.asyncio
async def test_get_user_tickets(db):
    await service.create_ticket(db, user_id=123, category="payment")
    await service.create_ticket(db, user_id=123, category="delivery")
    tickets = await service.get_user_tickets(db, 123)
    assert len(tickets) == 2


@pytest.mark.asyncio
async def test_get_new_tickets(db):
    await service.create_ticket(db, user_id=123, category="payment")
    await service.create_ticket(db, user_id=456, category="delivery")
    tickets = await service.get_new_tickets(db)
    assert len(tickets) == 2


@pytest.mark.asyncio
async def test_add_feedback(db):
    ticket_id = await service.create_ticket(db, user_id=123, category="payment")
    await service.add_feedback(db, ticket_id, 5, "Great!")

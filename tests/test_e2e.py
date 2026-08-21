from __future__ import annotations

import pytest

from src.core.ui import ticket_card
from src.support import service


@pytest.mark.asyncio
async def test_full_ticket_flow(db):
    ticket_id = await service.create_ticket(
        db, user_id=111, category="payment", subject="Can't pay"
    )
    assert ticket_id > 0

    taken = await service.take_ticket(db, ticket_id, 222)
    assert taken is True

    await service.add_message(
        db, ticket_id=ticket_id, sender_id=222, sender_role="manager", text_content="We'll help"
    )

    await service.close_ticket(db, ticket_id)
    ticket = await service.get_ticket(db, ticket_id)
    assert ticket["status"] == "closed"


@pytest.mark.asyncio
async def test_two_managers_race(db):
    ticket_id = await service.create_ticket(db, user_id=111, category="payment")
    first = await service.take_ticket(db, ticket_id, 222)
    second = await service.take_ticket(db, ticket_id, 333)
    assert first is True
    assert second is False
    ticket = await service.get_ticket(db, ticket_id)
    assert ticket["manager_id"] == 222


@pytest.mark.asyncio
async def test_ticket_card_html():
    card = ticket_card({
        "id": 1,
        "category": "delivery",
        "subject": "Test <script>",
        "status": "new",
    })
    assert "<script>" not in card
    assert "Тикет #1" in card

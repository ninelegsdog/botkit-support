from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.config import Config
from src.core.database import Database


@pytest.fixture
async def temp_db():
    config = Config(db_path=":memory:")
    database = Database(config)
    from src.core.migrations import migrate
    await migrate(database)
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_sla_check_loop_increments():
    from src.core.config import Config
    from src.sla.scheduler import sla_check_loop

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)

    bot = MagicMock()
    bot.send_message = AsyncMock()

    import asyncio
    task = asyncio.create_task(sla_check_loop(bot, db))
    await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await db.close()


@pytest.mark.asyncio
async def test_service_escalate_ticket():
    from src.core.config import Config
    from src.support.service import create_ticket, escalate_ticket, get_ticket

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    ticket_id = await create_ticket(db, user_id=1, category="payment", subject="Test")
    await escalate_ticket(db, ticket_id)
    _ticket = await get_ticket(db, ticket_id)
    await db.close()


@pytest.mark.asyncio
async def test_service_get_overdue_tickets():
    from src.core.config import Config
    from src.support.service import create_ticket, get_overdue_tickets

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    _fire_at = datetime.now(UTC) - timedelta(hours=25)
    _ticket_id = await create_ticket(db, user_id=1, category="payment", subject="Old")
    overdue = await get_overdue_tickets(db)
    assert isinstance(overdue, list)
    await db.close()


@pytest.mark.asyncio
async def test_service_get_canned_responses():
    from src.core.config import Config
    from src.support.service import get_canned_responses

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    canned = await get_canned_responses(db)
    assert isinstance(canned, list)
    await db.close()


@pytest.mark.asyncio
async def test_service_get_ticket_stats():
    from src.core.config import Config
    from src.support.service import create_ticket, get_ticket_stats

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    await create_ticket(db, user_id=1, category="payment", subject="Test")
    stats = await get_ticket_stats(db, "day")
    assert isinstance(stats, dict)
    await db.close()


@pytest.mark.asyncio
async def test_service_get_manager_stats():
    from src.core.config import Config
    from src.support.service import create_ticket, get_manager_stats, take_ticket

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    ticket_id = await create_ticket(db, user_id=1, category="payment", subject="Test")
    await take_ticket(db, ticket_id, 456)
    stats = await get_manager_stats(db, 456)
    assert isinstance(stats, dict)
    await db.close()


@pytest.mark.asyncio
async def test_service_get_active_managers():
    from src.core.config import Config
    from src.support.service import get_active_managers

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    managers = await get_active_managers(db)
    assert isinstance(managers, list)
    await db.close()


@pytest.mark.asyncio
async def test_service_add_ticket_note():
    from src.core.config import Config
    from src.support.service import add_ticket_note, create_ticket, get_ticket_notes

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    ticket_id = await create_ticket(db, user_id=1, category="payment", subject="Test")
    await add_ticket_note(db, ticket_id=ticket_id, manager_id=456, note="Internal note")
    notes = await get_ticket_notes(db, ticket_id)
    assert isinstance(notes, list)
    await db.close()


@pytest.mark.asyncio
async def test_ui_escape():
    from src.core.ui import escape
    assert escape("<script>") == "&lt;script&gt;"
    assert escape("hello") == "hello"


@pytest.mark.asyncio
async def test_ui_ticket_card():
    from src.core.ui import ticket_card
    card = ticket_card({
        "id": 1,
        "category": "payment",
        "subject": "Test <script>",
        "status": "new",
    })
    assert "<script>" not in card
    assert "Тикет #1" in card

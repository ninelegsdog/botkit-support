from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.config import Config
from src.core.database import Database
from src.core.metrics import Metrics


@pytest.fixture
async def temp_db():
    config = Config(db_path=":memory:")
    database = Database(config)
    from src.core.migrations import migrate
    await migrate(database)
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_database_context_manager(temp_db: Database) -> None:
    async with temp_db.session() as session:
        assert session is not None
    await temp_db.close()


@pytest.mark.asyncio
async def test_metrics():
    m = Metrics()
    m.tickets_created = 1
    m.messages_processed = 1
    m.sla_violations = 1
    m.errors = 1
    assert m.tickets_created == 1
    assert m.messages_processed == 1
    assert m.sla_violations == 1
    assert m.errors == 1
    assert m.uptime_seconds() >= 0


@pytest.mark.asyncio
async def test_config_validation():
    cfg = Config(
        bot_token="123:ABC",
        admin_password="secret",
        admin_ids=[1],
    )
    cfg.validate()


@pytest.mark.asyncio
async def test_sla_check_loop():
    from src.core.config import Config
    from src.sla.scheduler import sla_check_loop

    _cfg = Config(
        bot_token="123:ABC",
        admin_password="secret",
        admin_ids=[1],
    )

    async def mock_send(user_id: int, text: str) -> None:
        pass

    bot = MagicMock()
    bot.send_message = AsyncMock()
    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)

    # Test that the function can be called (we won't run the infinite loop)
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
async def test_service_create_ticket():
    from src.core.config import Config
    from src.support.service import create_ticket

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    ticket_id = await create_ticket(db, user_id=1, category="payment", subject="Test")
    assert ticket_id > 0
    await db.close()


@pytest.mark.asyncio
async def test_service_get_ticket():
    from src.core.config import Config
    from src.support.service import create_ticket, get_ticket

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    ticket_id = await create_ticket(db, user_id=1, category="payment", subject="Test")
    ticket = await get_ticket(db, ticket_id)
    assert ticket is not None
    assert ticket["category"] == "payment"
    await db.close()


@pytest.mark.asyncio
async def test_service_take_ticket():
    from src.core.config import Config
    from src.support.service import create_ticket, take_ticket

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    ticket_id = await create_ticket(db, user_id=1, category="payment", subject="Test")
    success = await take_ticket(db, ticket_id, 456)
    assert success is True
    await db.close()


@pytest.mark.asyncio
async def test_service_add_message():
    from src.core.config import Config
    from src.support.service import add_message, create_ticket, get_ticket_messages

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    ticket_id = await create_ticket(db, user_id=1, category="payment", subject="Test")
    await add_message(db, ticket_id=ticket_id, sender_id=1, sender_role="client", text_content="Hello")
    messages = await get_ticket_messages(db, ticket_id)
    assert len(messages) >= 1
    await db.close()


@pytest.mark.asyncio
async def test_service_close_ticket():
    from src.core.config import Config
    from src.support.service import close_ticket, create_ticket, get_ticket, take_ticket

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    ticket_id = await create_ticket(db, user_id=1, category="payment", subject="Test")
    await take_ticket(db, ticket_id, 456)
    await close_ticket(db, ticket_id)
    ticket = await get_ticket(db, ticket_id)
    assert ticket["status"] == "closed"
    await db.close()


@pytest.mark.asyncio
async def test_service_get_user_tickets():
    from src.core.config import Config
    from src.support.service import create_ticket, get_user_tickets

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    await create_ticket(db, user_id=1, category="payment", subject="Test1")
    await create_ticket(db, user_id=1, category="delivery", subject="Test2")
    tickets = await get_user_tickets(db, 1)
    assert len(tickets) == 2
    await db.close()


@pytest.mark.asyncio
async def test_service_get_new_tickets():
    from src.core.config import Config
    from src.support.service import create_ticket, get_new_tickets

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    await create_ticket(db, user_id=1, category="payment", subject="Test")
    await create_ticket(db, user_id=2, category="delivery", subject="Test")
    tickets = await get_new_tickets(db)
    assert len(tickets) == 2
    await db.close()


@pytest.mark.asyncio
async def test_service_add_feedback():
    from src.core.config import Config
    from src.support.service import add_feedback, create_ticket

    config = Config(db_path=":memory:")
    db = Database(config)
    from src.core.migrations import migrate
    await migrate(db)
    ticket_id = await create_ticket(db, user_id=1, category="payment", subject="Test")
    await add_feedback(db, ticket_id, 5, "Great!")
    await db.close()

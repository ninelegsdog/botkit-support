from __future__ import annotations

from typing import Any

import pytest

from src.core.config import Config
from src.core.database import Database
from src.core.migrations import migrate as run_migrate
from src.support import service


@pytest.fixture
async def db(tmp_path: Any) -> Database:
    database = Database(Config(bot_token="", db_path=str(tmp_path / "t.db")))
    await run_migrate(database)
    yield database
    await database.close()


async def test_manager_reply_role_is_manager(db: Database) -> None:
    ticket_id = await service.create_ticket(db, user_id=42, category="billing", subject="q")
    await service.add_message(
        db, ticket_id=ticket_id, sender_id=7, sender_role="manager", text_content="answer"
    )
    msgs = await service.get_ticket_messages(db, ticket_id)
    roles = [m["sender_role"] for m in msgs]
    assert roles == ["client", "manager"]


async def test_internal_notes_hidden_from_client_dialog(db: Database) -> None:
    ticket_id = await service.create_ticket(db, user_id=42, category="tech", subject="bug")
    await service.add_ticket_note(
        db, ticket_id=ticket_id, manager_id=7, note="проверить счёт"
    )
    notes = await service.get_ticket_notes(db, ticket_id)
    assert len(notes) == 1 and notes[0]["text"] == "проверить счёт"

    dialog = await service.get_ticket_messages(db, ticket_id)
    assert all(m["sender_role"] != "note" for m in dialog)


async def test_canned_body_lookup(db: Database) -> None:
    async with db.transaction() as session:
        from sqlalchemy import text

        await session.execute(
            text(
                "INSERT INTO canned_responses (title, body) VALUES ('Как оплатить', 'Ссылка...')"
            )
        )
        row = await session.execute(text("SELECT id FROM canned_responses LIMIT 1"))
        cid = int(row.scalar_one())
    assert await service.get_canned_body(db, cid) == "Ссылка..."
    assert await service.get_canned_body(db, 9999) is None

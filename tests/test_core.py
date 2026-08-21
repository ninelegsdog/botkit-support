from __future__ import annotations

import pytest

from src.core.config import Config
from src.core.ui import escape, ticket_card, ticket_message


@pytest.mark.asyncio
async def test_config_from_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "test_token")
    config = Config.from_env()
    assert config.bot_token == "test_token"


def test_escape():
    assert escape("<script>") == "&lt;script&gt;"
    assert escape("hello") == "hello"
    assert escape(None) == ""


def test_ticket_card():
    card = ticket_card({
        "id": 1,
        "category": "payment",
        "subject": "Test <script>",
        "status": "new",
    })
    assert "<script>" not in card
    assert "Тикет #1" in card


def test_ticket_message():
    msg = ticket_message({
        "sender_role": "client",
        "text": "Hello <b>world</b>",
    })
    assert "<b>" not in msg
    assert "Клиент" in msg

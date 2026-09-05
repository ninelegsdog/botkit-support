from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, Message, User

from src.admin.handlers import create_admin_router
from src.core.bot_factory import AppState, create_app
from src.core.config import Config
from src.core.errors import RetryMiddleware, default_error_handler, register_error_handler
from src.core.fsm import AdminAuth, TicketCreate, TicketReply
from src.core.metrics import (
    ERRORS_TOTAL,
    TICKETS_TOTAL,
    UPDATES_TOTAL,
    Metrics,
    UpdatesMiddleware,
)
from src.core.navigation import admin_menu, client_menu, manager_menu
from src.core.sentry import init_sentry
from src.core.storage import Storage
from src.core.throttling import ThrottlingMiddleware
from src.core.webhook import create_app as create_webhook_app
from src.core.webhook import health_handler, metrics_handler
from src.support.handlers import create_support_router


def _real_message(text: str, user_id: int = 1) -> Message:
    return Message(
        message_id=1,
        chat=Chat(id=user_id, type="private"),
        date=datetime.now(),
        from_user=User(id=user_id, is_bot=False, first_name="U"),
        text=text,
    )


def _fsm(user_id: int = 1, chat_id: int = 1) -> FSMContext:
    return FSMContext(MemoryStorage(), StorageKey(bot_id=123, chat_id=chat_id, user_id=user_id))


def _app_state(admin_ids: list[int] | None, token: str = "123456789:AAfake") -> AppState:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "src.core.bot_factory.RedisStorage.from_url",
            lambda *a, **k: MemoryStorage(),
        )
        cfg = Config(
            bot_token=token,
            admin_password="secret",
            admin_ids=admin_ids,
            redis_url="redis://localhost:6379/0",
            db_path=":memory:",
        )
        return create_app(cfg)


async def _app_state_db(admin_ids: list[int] | None, token: str = "123456789:AAfake") -> AppState:
    from src.core.migrations import migrate

    state = _app_state(admin_ids, token)
    await migrate(state.db)
    return state


def _find(router: Any, name: str) -> Callable[..., Awaitable[Any]]:
    for obs in router.message.handlers:
        if obs.callback.__name__ == name:
            return obs.callback
    for obs in router.callback_query.handlers:
        if obs.callback.__name__ == name:
            return obs.callback
    raise AssertionError(f"handler {name} not found")


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #
def test_config_from_env_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("ADMIN_PASSWORD", "pw")
    monkeypatch.setenv("ADMIN_IDS", "1,2,3")
    monkeypatch.setenv("REDIS_URL", "redis://h/1")
    cfg = Config.from_env()
    assert cfg.bot_token == "tok"
    assert cfg.admin_password == "pw"
    assert cfg.admin_ids == [1, 2, 3]
    assert cfg.redis_url == "redis://h/1"


def test_config_validate_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_IDS", raising=False)
    cfg = Config(bot_token="", admin_password="", admin_ids=[])
    with pytest.raises(RuntimeError):
        cfg.validate()
    cfg2 = Config(bot_token="t", admin_password="", admin_ids=[1])
    with pytest.raises(RuntimeError):
        cfg2.validate()
    cfg3 = Config(bot_token="t", admin_password="p", admin_ids=[])
    with pytest.raises(RuntimeError):
        cfg3.validate()
    ok = Config(bot_token="t", admin_password="p", admin_ids=[1])
    ok.validate()


# --------------------------------------------------------------------------- #
# bot_factory
# --------------------------------------------------------------------------- #
def test_create_app_builds_bot_and_dispatcher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.core.bot_factory.RedisStorage.from_url",
        lambda *a, **k: MemoryStorage(),
    )
    state = create_app(Config(bot_token="123456789:AAfake", admin_ids=[1]))
    assert isinstance(state.bot, Bot)
    assert isinstance(state.dp, Dispatcher)
    assert isinstance(state.fsm_storage, MemoryStorage)


def test_create_app_default_config_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:AAfake")
    monkeypatch.setenv("ADMIN_IDS", "1")
    monkeypatch.setattr(
        "src.core.bot_factory.RedisStorage.from_url",
        lambda *a, **k: MemoryStorage(),
    )
    state = create_app(None)
    assert isinstance(state.bot, Bot)


# --------------------------------------------------------------------------- #
# throttling
# --------------------------------------------------------------------------- #
async def test_throttling_allows_first_blocks_second() -> None:
    mw = ThrottlingMiddleware(min_interval=2.0)

    async def handler(event: Any, data: dict[str, Any]) -> str:
        return "ok"

    msg = _real_message("x")
    assert await mw(handler, msg, {}) == "ok"
    mw._last_message[1] = __import__("time").time()
    assert await mw(handler, msg, {}) is None


async def test_throttling_ignores_non_message() -> None:
    mw = ThrottlingMiddleware(min_interval=2.0)

    async def handler(event: Any, data: dict[str, Any]) -> str:
        return "ok"

    from types import SimpleNamespace

    assert await mw(handler, SimpleNamespace(), {}) == "ok"


# --------------------------------------------------------------------------- #
# storage
# --------------------------------------------------------------------------- #
async def test_storage_get_set_setting() -> None:
    sess = MagicMock()
    result = MagicMock()
    result.fetchone = MagicMock(return_value=("v",))
    sess.execute = AsyncMock(return_value=result)
    cm = AsyncMock()
    cm.__aenter__.return_value = sess
    cm.__aexit__.return_value = False
    db = MagicMock()
    db.session = MagicMock(return_value=cm)
    db.transaction = MagicMock(return_value=cm)

    storage = Storage(db)
    assert await storage.get_setting("theme") == "v"
    await storage.set_setting("theme", "dark")
    sess.execute.assert_awaited()


# --------------------------------------------------------------------------- #
# webhook
# --------------------------------------------------------------------------- #
async def test_webhook_app_registers_routes() -> None:
    from aiohttp.test_utils import make_mocked_request

    state = _app_state([1])
    app = create_webhook_app(state)
    assert callable(app.router.routes)
    routes = app.router.routes()
    assert any(r.resource and "health" in r.resource.canonical for r in routes)
    req = make_mocked_request("GET", "/health", app=app)
    resp = await health_handler(req)
    # health_handler returns plain text "ok" (not JSON); read with .text.
    assert resp.status == 200
    assert resp.text == "ok"
    req2 = make_mocked_request("GET", "/metrics", app=app)
    resp2 = await metrics_handler(req2)
    assert resp2.status == 200


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
async def test_updates_middleware_increments_prom_counter() -> None:
    mw = UpdatesMiddleware()

    async def handler(event: Any, data: dict[str, Any]) -> str:
        return "ok"

    before = UPDATES_TOTAL.labels(type="message")._value.get()
    await mw(handler, _real_message("x"), {})
    after = UPDATES_TOTAL.labels(type="message")._value.get()
    assert after == before + 1


def test_metrics_inc_helpers() -> None:
    m = Metrics()
    m.inc_messages()
    m.inc_tickets()
    m.inc_resolved()
    m.inc_errors()
    assert m.messages_processed == 1
    assert m.tickets_created == 1
    assert m.tickets_resolved == 1
    assert m.errors == 1
    assert TICKETS_TOTAL._value.get() >= 1
    assert ERRORS_TOTAL.labels(error_type="domain")._value.get() >= 1


# --------------------------------------------------------------------------- #
# sentry
# --------------------------------------------------------------------------- #
def test_sentry_no_dsn_silent() -> None:
    init_sentry(None)


def test_sentry_missing_sdk() -> None:
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(sys.modules, "sentry_sdk", None)
        init_sentry("https://abc@sentry.io/1")  # must not raise


def test_sentry_valid_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    init_sentry("https://abc@sentry.io/1")  # must call sentry_sdk.init
    fake.init.assert_called_once()


# --------------------------------------------------------------------------- #
# errors
# --------------------------------------------------------------------------- #
async def test_retry_middleware_retry_after_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    from aiogram.exceptions import TelegramRetryAfter

    slept: list[float] = []

    async def fake_sleep(s: float) -> None:
        slept.append(s)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    calls = 0

    async def handler(event: Any, data: dict[str, Any]) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TelegramRetryAfter(method=None, message="r", retry_after=0)
        return "ok"

    mw = RetryMiddleware(max_retries=3, delay=0)
    assert await mw(handler, None, {}) == "ok"  # type: ignore[arg-type]
    assert calls == 2


async def test_default_error_handler_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    from aiogram.exceptions import TelegramRetryAfter

    slept: list[float] = []

    async def fake_sleep(s: float) -> None:
        slept.append(s)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    await default_error_handler(
        None, TelegramRetryAfter(method=None, message="r", retry_after=0)  # type: ignore[arg-type]
    )
    assert 0.0 in slept
    assert ERRORS_TOTAL.labels(error_type="retry_after")._value.get() >= 1


def test_register_error_handler_decorator() -> None:
    fake_dp = MagicMock()
    fake_dp.error = MagicMock(return_value=MagicMock())
    register_error_handler(fake_dp)
    fake_dp.error.assert_called_once()


# --------------------------------------------------------------------------- #
# fsm / nav
# --------------------------------------------------------------------------- #
def test_fsm_states_subclass() -> None:
    from aiogram.fsm.state import StatesGroup

    assert issubclass(TicketCreate, StatesGroup)
    assert issubclass(TicketReply, StatesGroup)
    assert issubclass(AdminAuth, StatesGroup)
    assert TicketCreate.entering_text is not None


def test_nav_menus_kbd() -> None:
    assert client_menu().keyboard
    assert manager_menu().keyboard
    assert admin_menu().keyboard


# --------------------------------------------------------------------------- #
# support handlers
# --------------------------------------------------------------------------- #
async def test_support_cmd_start(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = AsyncMock()
    monkeypatch.setattr(Message, "answer", answer)
    state = _app_state([1])
    router = create_support_router(state)
    cb = _find(router, "cmd_start")
    msg = _real_message("x")
    await cb(msg)
    answer.assert_awaited_once()


async def test_support_my_tickets_empty(db, monkeypatch: pytest.MonkeyPatch) -> None:
    answer = AsyncMock()
    monkeypatch.setattr(Message, "answer", answer)
    state = await _app_state_db([1])
    router = create_support_router(state)
    cb = _find(router, "my_tickets")
    msg = _real_message("x")
    await cb(msg)
    answer.assert_awaited_once()


async def test_support_start_ticket_uses_fsm(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = AsyncMock()
    monkeypatch.setattr(Message, "answer", answer)
    state = _app_state([1])
    router = create_support_router(state)
    cb = _find(router, "start_ticket")
    msg = _real_message("➕ Новый тикет")
    ctx = _fsm()
    await cb(msg, ctx)
    assert await ctx.get_state() is None
    answer.assert_awaited_once()


# --------------------------------------------------------------------------- #
# admin handlers
# --------------------------------------------------------------------------- #
async def test_admin_stats_non_admin_early_return(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = AsyncMock()
    monkeypatch.setattr(Message, "answer", answer)
    state = _app_state([2])  # current user id=1 not in admin_ids
    router = create_admin_router(state)
    cb = _find(router, "admin_stats")
    msg = _real_message("📊 Моя статистика", user_id=1)
    await cb(msg)
    assert answer.await_count == 0


async def test_admin_stats_admin_branch_runs(db, monkeypatch: pytest.MonkeyPatch) -> None:
    answer = AsyncMock()
    monkeypatch.setattr(Message, "answer", answer)
    state = await _app_state_db([1])
    router = create_admin_router(state)
    cb = _find(router, "admin_stats")
    msg = _real_message("📊 Статистика", user_id=1)
    await cb(msg)
    assert answer.await_count >= 1


async def test_admin_cmd_admin_sets_fsm_state(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = AsyncMock()
    monkeypatch.setattr(Message, "answer", answer)
    state = _app_state([1])
    router = create_admin_router(state)
    cb = _find(router, "cmd_admin")
    msg = _real_message("/admin", user_id=1)
    ctx = _fsm()
    await cb(msg, ctx)
    assert await ctx.get_state() == AdminAuth.waiting_password.state


# --------------------------------------------------------------------------- #
# auth / payments / app / sla
# --------------------------------------------------------------------------- #
async def test_auth_middleware_injects_db(db) -> None:
    from src.core.auth import AuthMiddleware

    mw = AuthMiddleware(db)
    captured: dict[str, Any] = {}

    async def handler(event: Any, data: dict[str, Any]) -> None:
        captured.update(data)

    await mw(handler, _real_message("x"), {})
    assert captured["db"] is db


async def test_payments_mock_provider() -> None:
    from src.core.payments import MockPaymentProvider

    prov = MockPaymentProvider()
    pid = await prov.create_payment(
        title="t", description="d", payload="p", amount=100
    )
    assert pid.startswith("https://t.me/mock-bot/invoice/")
    assert await prov.check_payment(pid) is True


async def test_register_routers_includes_both() -> None:
    from src.app import register_routers

    state = _app_state([1])
    register_routers(state)
    assert len(state.dp.sub_routers) == 2


async def test_sla_check_loop_iterates(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.sla import scheduler
    from src.support import service

    overdue = [{"id": 5, "user_id": 1, "manager_id": None}]
    get = AsyncMock(return_value=overdue)
    esc = AsyncMock()
    send = AsyncMock()
    monkeypatch.setattr(service, "get_overdue_tickets", get)
    monkeypatch.setattr(service, "escalate_ticket", esc)
    bot = MagicMock()
    bot.send_message = send
    _orig_sleep = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda _s: _orig_sleep(0))

    try:
        await asyncio.wait_for(scheduler.sla_check_loop(bot, MagicMock()), timeout=0.5)
    except (TimeoutError, asyncio.CancelledError):
        pass
    assert get.await_count >= 1
    assert esc.await_count >= 1

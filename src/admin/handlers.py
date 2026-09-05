from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.core.bot_factory import AppState
from src.core.fsm import AdminAuth
from src.core.navigation import admin_menu, client_menu
from src.support import service


def create_admin_router(app_state: AppState) -> Router:
    router = Router()
    db = app_state.db

    def is_admin(user_id: int) -> bool:
        return user_id in (app_state.config.admin_ids or [])

    @router.message(Command("admin"))
    async def cmd_admin(message: Message, state: FSMContext) -> None:
        await state.set_state(AdminAuth.waiting_password)
        await message.answer("🔑 Введите пароль:")

    @router.message(AdminAuth.waiting_password)
    async def check_password(message: Message, state: FSMContext) -> None:
        if message.text == app_state.config.admin_password:
            await state.clear()
            await message.answer("✅ Добро пожаловать!", reply_markup=admin_menu())
        else:
            await state.clear()
            await message.answer("❌ Неверный пароль.", reply_markup=client_menu())

    @router.message(F.text == "👥 Менеджеры")
    async def list_managers(message: Message) -> None:
        if not is_admin(message.from_user.id):  # type: ignore[union-attr]
            return
        managers = await service.get_active_managers(db)
        if not managers:
            await message.answer("Менеджеров нет.")
            return
        text = "👥 Менеджеры:\n" + "\n".join(
            f"• {m['name']} (ID: {m['user_id']})" for m in managers
        )
        await message.answer(text)

    @router.message(F.text == "📊 Статистика")
    async def admin_stats(message: Message) -> None:
        if not is_admin(message.from_user.id):  # type: ignore[union-attr]
            return
        day = await service.get_ticket_stats(db, "day")
        week = await service.get_ticket_stats(db, "week")
        await message.answer(
            f"📊 Статистика:\n\nСегодня:\n  Новых: {day.get('new', 0)}\n"
            f"  В работе: {day.get('taken', 0) + day.get('in_progress', 0)}\n"
            f"  Закрытых: {day.get('closed', 0)}\n\n"
            f"За неделю:\n  Новых: {week.get('new', 0)}\n"
            f"  В работе: {week.get('taken', 0) + week.get('in_progress', 0)}\n"
            f"  Закрытых: {week.get('closed', 0)}"
        )

    @router.message(F.text == "⚙️ SLA")
    async def admin_sla(message: Message) -> None:
        if not is_admin(message.from_user.id):  # type: ignore[union-attr]
            return
        await message.answer(
            "⚙️ SLA настройки:\n"
            f"• Ответ: {app_state.config.sla_reply_minutes} мин\n"
            f"• Закрытие: {app_state.config.sla_close_hours} ч"
        )

    @router.message(F.text == "⚡ Шаблоны")
    async def admin_canned(message: Message) -> None:
        if not is_admin(message.from_user.id):  # type: ignore[union-attr]
            return
        await message.answer("⚡ Управление шаблонами ответов (v1.1)")

    return router

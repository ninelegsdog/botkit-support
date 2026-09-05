from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.core.bot_factory import AppState
from src.core.fsm import TicketCreate, TicketReply
from src.core.navigation import client_menu
from src.core.ui import escape, ticket_card
from src.support import service


def create_support_router(app_state: AppState) -> Router:
    router = Router()
    db = app_state.db

    @router.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        await message.answer(
            "👋 Здравствуйте! Чем можем помочь?",
            reply_markup=client_menu(),
        )

    @router.message(F.text == "➕ Новый тикет")
    async def start_ticket(message: Message, state: FSMContext) -> None:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплата", callback_data="ticket_cat:payment")],
                [InlineKeyboardButton(text="🚚 Доставка", callback_data="ticket_cat:delivery")],
                [InlineKeyboardButton(text="🔧 Техника", callback_data="ticket_cat:technical")],
                [InlineKeyboardButton(text="💬 Другое", callback_data="ticket_cat:other")],
            ]
        )
        await message.answer("Выберите категорию:", reply_markup=kb)

    @router.callback_query(F.data.startswith("ticket_cat:"))
    async def choose_category(callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.data:
            return
        category = callback.data.split(":", 1)[1]
        await state.update_data(category=category)
        await state.set_state(TicketCreate.entering_text)
        await callback.message.edit_text("Опишите проблему:")  # type: ignore
        await callback.answer()

    @router.message(TicketCreate.entering_text)
    async def enter_text(message: Message, state: FSMContext) -> None:
        await state.update_data(subject=message.text or "")
        data = await state.get_data()
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Создать", callback_data="ticket_confirm"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="ticket_cancel"),
                ]
            ]
        )
        await state.set_state(TicketCreate.confirming)
        await message.answer(
            f"Создать тикет?\nКатегория: {escape(str(data.get('category', '')))}\n"
            f"Описание: {escape(str(data.get('subject', '')))}",
            reply_markup=kb,
        )

    @router.callback_query(F.data == "ticket_confirm", TicketCreate.confirming)
    async def confirm_ticket(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        ticket_id = await service.create_ticket(
            db,
            user_id=callback.from_user.id,
            category=str(data.get("category", "other")),
            subject=str(data.get("subject", "")),
        )
        app_state.metrics.inc_tickets()
        await state.clear()
        await callback.message.edit_text(  # type: ignore
            f"✅ Тикет #{ticket_id} создан. Менеджер ответит в течение 30 минут."
        )
        await callback.answer()
        await callback.message.answer("Выберите действие:", reply_markup=client_menu())  # type: ignore

        managers = await service.get_active_managers(db)
        card = ticket_card({
            "id": ticket_id,
            "category": data.get("category", ""),
            "subject": data.get("subject", ""),
            "status": "new",
        })
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Взять", callback_data=f"ticket_take:{ticket_id}"),
                    InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"ticket_skip:{ticket_id}"),
                ]
            ]
        )
        for mgr in managers:
            try:
                await app_state.bot.send_message(int(str(mgr["user_id"])), card, reply_markup=kb)
            except Exception as e:
                logger.warning("notify failed: %s", e)

    @router.callback_query(F.data == "ticket_cancel")
    async def cancel_ticket(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await callback.message.edit_text("Тикет отменён.")  # type: ignore
        await callback.answer()
        await callback.message.answer("Выберите действие:", reply_markup=client_menu())  # type: ignore

    @router.message(F.text == "📋 Мои тикеты")
    async def my_tickets(message: Message) -> None:
        tickets = await service.get_user_tickets(db, message.from_user.id)  # type: ignore[union-attr]
        if not tickets:
            await message.answer("У вас нет тикетов.")
            return
        for t in tickets[:10]:
            card = ticket_card(t)
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="💬 Ответить", callback_data=f"ticket_reply:{t['id']}"),
                        InlineKeyboardButton(text="✅ Закрыть", callback_data=f"ticket_close:{t['id']}"),
                    ]
                ]
            )
            await message.answer(card, reply_markup=kb)

    @router.callback_query(F.data.startswith("ticket_reply:"))
    async def start_reply(callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.data:
            return
        ticket_id = int(callback.data.split(":")[1])
        await state.update_data(ticket_id=ticket_id)
        await state.set_state(TicketReply.entering_reply)
        canned = await service.get_canned_responses(db)
        rows = [
            [InlineKeyboardButton(text=c["title"], callback_data=f"canned:{c['id']}")]
            for c in canned[:6]
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
        await callback.message.edit_text("Напишите ответ (или выберите шаблон):", reply_markup=kb)  # type: ignore
        await callback.answer()

    @router.callback_query(F.data.startswith("canned:"))
    async def use_canned(callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.data:
            return
        cid = int(callback.data.split(":")[1])
        body = await service.get_canned_body(db, cid)
        if not body:
            await callback.answer("Шаблон не найден.")
            return
        await state.update_data(canned_body=body)
        await callback.message.edit_text(f"Ответ (шаблон):\n{body}\n\nОтправить? ✅ / ✏️ напишите свой.")  # type: ignore
        await callback.answer("Теперь отправьте /send или свой текст.")

    @router.message(Command("send"), TicketReply.entering_reply)
    async def send_canned_reply(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        ticket_id = int(str(data.get("ticket_id", 0)))
        body = str(data.get("canned_body", ""))
        await service.add_message(
            db,
            ticket_id=ticket_id,
            sender_id=message.from_user.id,  # type: ignore[union-attr]
            sender_role="manager",
            text_content=body,
        )
        await state.clear()
        await message.answer(f"✅ Ответ отправлен по тикету #{ticket_id}.")

    @router.message(TicketReply.entering_reply)
    async def send_reply(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        ticket_id = int(str(data.get("ticket_id", 0)))
        await service.add_message(
            db,
            ticket_id=ticket_id,
            sender_id=message.from_user.id,  # type: ignore[union-attr]
            sender_role="manager",
            text_content=message.text or "",
        )
        await state.clear()
        await message.answer(f"✅ Ответ отправлен по тикету #{ticket_id}.")
        ticket = await service.get_ticket(db, ticket_id)
        if ticket and ticket.get("manager_id"):
            try:
                await app_state.bot.send_message(
                    int(str(ticket["manager_id"])),
                    f"💬 Клиент ответил по тикету #{ticket_id}: {message.text}",
                )
            except Exception as e:
                logger.warning("notify failed: %s", e)

    @router.callback_query(F.data.startswith("ticket_close:"))
    async def close_ticket_handler(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        ticket_id = int(callback.data.split(":")[1])
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да", callback_data=f"ticket_close_yes:{ticket_id}"),
                    InlineKeyboardButton(text="❌ Нет", callback_data=f"ticket_close_no:{ticket_id}"),
                ]
            ]
        )
        await callback.message.edit_text("❓ Закрыть тикет?", reply_markup=kb)  # type: ignore
        await callback.answer()

    @router.callback_query(F.data.startswith("ticket_close_yes:"))
    async def confirm_close(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        ticket_id = int(callback.data.split(":")[1])
        await service.close_ticket(db, ticket_id)
        await callback.message.edit_text("✅ Тикет закрыт.")  # type: ignore
        await callback.answer()

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="⭐1", callback_data=f"ticket_rate:{ticket_id}:1"),
                    InlineKeyboardButton(text="⭐2", callback_data=f"ticket_rate:{ticket_id}:2"),
                    InlineKeyboardButton(text="⭐3", callback_data=f"ticket_rate:{ticket_id}:3"),
                    InlineKeyboardButton(text="⭐4", callback_data=f"ticket_rate:{ticket_id}:4"),
                    InlineKeyboardButton(text="⭐5", callback_data=f"ticket_rate:{ticket_id}:5"),
                ]
            ]
        )
        try:
            await callback.message.answer("Оцените качество: ⭐1-5", reply_markup=kb)  # type: ignore
        except Exception as e:
            logger.warning("rate request failed: %s", e)

    @router.callback_query(F.data.startswith("ticket_close_no:"))
    async def cancel_close(callback: CallbackQuery) -> None:
        await callback.message.edit_text("Тикет остаётся открытым.")  # type: ignore
        await callback.answer()

    @router.callback_query(F.data.startswith("ticket_rate:"))
    async def rate_ticket(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        parts = callback.data.split(":")
        ticket_id = int(parts[1])
        rating = int(parts[2])
        await service.add_feedback(db, ticket_id, rating, "")
        await callback.message.edit_text(f"Спасибо за оценку: {'⭐' * rating}")  # type: ignore
        await callback.answer()

    @router.callback_query(F.data.startswith("ticket_take:"))
    async def take_ticket_handler(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        ticket_id = int(callback.data.split(":")[1])
        success = await service.take_ticket(db, ticket_id, callback.from_user.id)
        if not success:
            await callback.answer("Тикет уже взят.", show_alert=True)
            return
        await callback.answer("✅ Тикет взят!")
        ticket = await service.get_ticket(db, ticket_id)
        if ticket:
            try:
                await app_state.bot.send_message(
                    int(str(ticket["user_id"])),
                    f"👋 Менеджер поможет вам по тикету #{ticket_id}.",
                )
            except Exception as e:
                logger.warning("notify failed: %s", e)

    @router.callback_query(F.data.startswith("ticket_skip:"))
    async def skip_ticket_handler(callback: CallbackQuery) -> None:
        await callback.answer("Пропущено.")

    @router.message(F.text == "📋 Очередь тикетов")
    async def manager_queue(message: Message) -> None:
        tickets = await service.get_new_tickets(db)
        if not tickets:
            await message.answer("Очередь пуста.")
            return
        for t in tickets[:10]:
            card = ticket_card(t)
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Взять", callback_data=f"ticket_take:{t['id']}"),
                        InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"ticket_skip:{t['id']}"),
                    ]
                ]
            )
            await message.answer(card, reply_markup=kb)

    @router.message(F.text == "📊 Моя статистика")
    async def my_stats(message: Message) -> None:
        stats = await service.get_manager_stats(db, message.from_user.id)  # type: ignore[union-attr]
        await message.answer(f"📊 Ваша статистика:\nЗакрытых тикетов: {stats['closed']}")

    return router


logger = logging.getLogger(__name__)

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.core.bot_factory import AppState
from src.core.callbacks import parse_callback_int
from src.core.fsm import TicketCreate, TicketReply
from src.core.navigation import client_menu
from src.core.ui import escape, ticket_card
from src.support import service, texts


def create_support_router(app_state: AppState) -> Router:
    router = Router()
    db = app_state.db

    @router.message(Command("start"))
    async def cmd_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(
            texts.WELCOME,
            reply_markup=client_menu(),
        )

    @router.message(F.text == "❓ Помощь")
    async def help_menu(message: Message) -> None:
        await message.answer(
            texts.HELP,
            reply_markup=client_menu(),
        )

    @router.message(F.text == "➕ Новый тикет")
    async def start_ticket(message: Message, state: FSMContext) -> None:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=texts.BTN_CAT_PAYMENT, callback_data="ticket_cat:payment")],
                [InlineKeyboardButton(text=texts.BTN_CAT_DELIVERY, callback_data="ticket_cat:delivery")],
                [InlineKeyboardButton(text=texts.BTN_CAT_TECHNICAL, callback_data="ticket_cat:technical")],
                [InlineKeyboardButton(text=texts.BTN_CAT_OTHER, callback_data="ticket_cat:other")],
            ]
        )
        await message.answer(texts.CHOOSE_CATEGORY, reply_markup=kb)

    @router.callback_query(F.data.startswith("ticket_cat:"))
    async def choose_category(callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.data:
            return
        category = callback.data.split(":", 1)[1]
        await state.update_data(category=category)
        await state.set_state(TicketCreate.entering_text)
        await callback.message.edit_text(texts.DESCRIBE_PROBLEM)  # type: ignore
        await callback.answer()

    @router.message(TicketCreate.entering_text)
    async def enter_text(message: Message, state: FSMContext) -> None:
        text = (message.text or "").strip()
        if not text:
            await message.answer(texts.EMPTY_DESCRIPTION)
            return
        await state.update_data(subject=text)
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
            texts.confirm_prompt(
                escape(str(data.get("category", ""))),
                escape(str(data.get("subject", ""))),
            ),
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
            sla_minutes=app_state.config.sla_reply_minutes,
        )
        app_state.metrics.inc_tickets()
        await state.clear()
        await callback.message.edit_text(  # type: ignore
            texts.ticket_created(ticket_id, app_state.config.sla_reply_minutes)
        )
        await callback.answer()
        await callback.message.answer(texts.CHOOSE_ACTION, reply_markup=client_menu())  # type: ignore

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
        await callback.message.edit_text(texts.TICKET_CANCELLED)  # type: ignore
        await callback.answer()
        await callback.message.answer(texts.CHOOSE_ACTION, reply_markup=client_menu())  # type: ignore

    @router.message(F.text == "📋 Мои тикеты")
    async def my_tickets(message: Message) -> None:
        tickets = await service.get_user_tickets(db, message.from_user.id)  # type: ignore[union-attr]
        if not tickets:
            await message.answer(texts.NO_TICKETS)
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
        ticket_id = parse_callback_int(callback.data, "ticket_reply:")
        if ticket_id is None:
            await callback.answer(texts.BAD_REQUEST, show_alert=True)
            return
        await state.update_data(ticket_id=ticket_id)
        await state.set_state(TicketReply.entering_reply)
        canned = await service.get_canned_responses(db)
        rows = [
            [InlineKeyboardButton(text=c["title"], callback_data=f"canned:{c['id']}")]
            for c in canned[:6]
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
        await callback.message.edit_text(texts.WRITE_REPLY, reply_markup=kb)  # type: ignore
        await callback.answer()

    @router.callback_query(F.data.startswith("canned:"))
    async def use_canned(callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.data:
            return
        cid = parse_callback_int(callback.data, "canned:")
        if cid is None:
            await callback.answer(texts.BAD_REQUEST, show_alert=True)
            return
        body = await service.get_canned_body(db, cid)
        if not body:
            await callback.answer(texts.CANNED_NOT_FOUND)
            return
        await state.update_data(canned_body=body)
        await callback.message.edit_text(texts.canned_preview(body))  # type: ignore
        await callback.answer(texts.CANNED_HINT)

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
            sla_close_hours=app_state.config.sla_close_hours,
        )
        await state.clear()
        await message.answer(texts.reply_sent(ticket_id))

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
            sla_close_hours=app_state.config.sla_close_hours,
        )
        await state.clear()
        await message.answer(texts.reply_sent(ticket_id))
        ticket = await service.get_ticket(db, ticket_id)
        if ticket and ticket.get("manager_id"):
            try:
                await app_state.bot.send_message(
                    int(str(ticket["manager_id"])),
                    texts.client_replied(ticket_id, message.text or ""),
                )
            except Exception as e:
                logger.warning("notify failed: %s", e)

    @router.callback_query(F.data.startswith("ticket_close:"))
    async def close_ticket_handler(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        ticket_id = parse_callback_int(callback.data, "ticket_close:")
        if ticket_id is None:
            await callback.answer(texts.BAD_REQUEST, show_alert=True)
            return
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да", callback_data=f"ticket_close_yes:{ticket_id}"),
                    InlineKeyboardButton(text="❌ Нет", callback_data=f"ticket_close_no:{ticket_id}"),
                ]
            ]
        )
        await callback.message.edit_text(texts.CONFIRM_CLOSE, reply_markup=kb)  # type: ignore
        await callback.answer()

    @router.callback_query(F.data.startswith("ticket_close_yes:"))
    async def confirm_close(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        ticket_id = parse_callback_int(callback.data, "ticket_close_yes:")
        if ticket_id is None:
            await callback.answer(texts.BAD_REQUEST, show_alert=True)
            return
        await service.close_ticket(db, ticket_id)
        await callback.message.edit_text(texts.TICKET_CLOSED)  # type: ignore
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
            await callback.message.answer(texts.RATE_PROMPT, reply_markup=kb)  # type: ignore
        except Exception as e:
            logger.warning("rate request failed: %s", e)

    @router.callback_query(F.data.startswith("ticket_close_no:"))
    async def cancel_close(callback: CallbackQuery) -> None:
        await callback.message.edit_text(texts.CLOSE_DECLINED)  # type: ignore
        await callback.answer()

    @router.callback_query(F.data.startswith("ticket_rate:"))
    async def rate_ticket(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        parts = callback.data.split(":")
        ticket_id = int(parts[1])
        rating = int(parts[2])
        await service.add_feedback(db, ticket_id, rating, "")
        await callback.message.edit_text(texts.thanked(rating))  # type: ignore
        await callback.answer()

    @router.callback_query(F.data.startswith("ticket_take:"))
    async def take_ticket_handler(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        ticket_id = parse_callback_int(callback.data, "ticket_take:")
        if ticket_id is None:
            await callback.answer(texts.BAD_REQUEST, show_alert=True)
            return
        success = await service.take_ticket(db, ticket_id, callback.from_user.id)
        if not success:
            await callback.answer(texts.TICKET_ALREADY_TAKEN, show_alert=True)
            return
        await callback.answer(texts.TICKET_TAKEN)
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

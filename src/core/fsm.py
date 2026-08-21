from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class TicketCreate(StatesGroup):
    choosing_category = State()
    entering_text = State()
    confirming = State()


class TicketReply(StatesGroup):
    entering_reply = State()


class TicketNote(StatesGroup):
    entering_note = State()


class AdminAuth(StatesGroup):
    waiting_password = State()

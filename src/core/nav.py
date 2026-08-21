from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def client_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Новый тикет"), KeyboardButton(text="📋 Мои тикеты")],
        ],
        resize_keyboard=True,
    )


def manager_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Очередь тикетов"), KeyboardButton(text="📊 Моя статистика")],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Менеджеры"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="⚙️ SLA"), KeyboardButton(text="⚡ Шаблоны")],
        ],
        resize_keyboard=True,
    )

from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


@dataclass(frozen=True)
class NavSection:
    slug: str
    title: str


class NavRegistry:
    def __init__(self) -> None:
        self._sections: dict[str, NavSection] = {}

    def register(self, section: NavSection) -> None:
        self._sections[section.slug] = section

    def get(self, slug: str) -> NavSection | None:
        return self._sections.get(slug)

    def title(self, slug: str) -> str:
        section = self.get(slug)
        return section.title if section else slug

    def breadcrumbs(self, slug: str) -> list[str]:
        return [self.title(slug)]


def client_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Новый тикет"), KeyboardButton(text="📋 Мои тикеты")],
            [KeyboardButton(text="❓ Помощь")],
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


def manager_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Очередь тикетов"), KeyboardButton(text="📊 Моя статистика")],
        ],
        resize_keyboard=True,
    )


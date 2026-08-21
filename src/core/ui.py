from __future__ import annotations

import html
from typing import Any


def escape(text: str | None) -> str:
    return html.escape(str(text)) if text else ""


def mask_phone(phone: str | None) -> str:
    if not phone or len(phone) < 7:
        return "***"
    return phone[:4] + "(***)" + phone[-2:]


def ticket_card(ticket: dict[str, Any], *, include_text: bool = True) -> str:
    lines = [
        f"🎫 Тикет #{ticket['id']}",
        f"Категория: {escape(str(ticket.get('category', '')))}",
        f"Статус: {_status_emoji(str(ticket.get('status', '')))} {escape(str(ticket.get('status', '')))}",
    ]
    if include_text and ticket.get("subject"):
        lines.append(f"Тема: {escape(str(ticket['subject']))}")
    if ticket.get("manager_id"):
        lines.append(f"Менеджер: ID {ticket['manager_id']}")
    return "\n".join(lines)


def ticket_message(msg: dict[str, Any]) -> str:
    role = str(msg.get("sender_role", "client"))
    labels = {
        "client": "👤 Клиент",
        "manager": "👨‍💼 Менеджер",
        "system": "🤖 Система",
        "note": "📝 Заметка",
    }
    role_label = labels.get(role, role)
    return f"{role_label}: {escape(str(msg.get('text', '')))}"


def _status_emoji(status: str) -> str:
    return {"new": "🆕", "taken": "⏳", "in_progress": "🔄", "closed": "✅"}.get(status, "❓")

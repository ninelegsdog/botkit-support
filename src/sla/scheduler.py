from __future__ import annotations

import asyncio

from aiogram import Bot

from src.core.database import Database
from src.support import service


async def sla_check_loop(bot: Bot, db: Database) -> None:
    while True:
        try:
            overdue = await service.get_overdue_tickets(db)
            for ticket in overdue:
                await service.escalate_ticket(db, int(ticket["id"]))
                try:
                    await bot.send_message(
                        int(str(ticket["user_id"])),
                        f"⏰ Тикет #{ticket['id']} просрочен. Мы ускорим ответ.",
                    )
                except Exception:
                    pass
                if ticket.get("manager_id"):
                    try:
                        await bot.send_message(
                            int(str(ticket["manager_id"])),
                            f"⏰ Тикет #{ticket['id']} просрочен по SLA!",
                        )
                    except Exception:
                        pass
        except Exception:
            pass
        await asyncio.sleep(60)

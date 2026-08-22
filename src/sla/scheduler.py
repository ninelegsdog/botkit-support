from __future__ import annotations

import asyncio
import logging

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
                except Exception as e:
                    logger.warning("SLA notify failed: %s", e)
                if ticket.get("manager_id"):
                    try:
                        await bot.send_message(
                            int(str(ticket["manager_id"])),
                            f"⏰ Тикет #{ticket['id']} просрочен по SLA!",
                        )
                    except Exception as e:
                        logger.warning("SLA manager notify failed: %s", e)
        except Exception as e:
            logger.error("SLA loop error: %s", e)
        await asyncio.sleep(60)


logger = logging.getLogger(__name__)

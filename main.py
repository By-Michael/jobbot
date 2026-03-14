"""
main.py — Entry point for the Telegram Job Finder Bot.

Startup sequence:
  1. Initialise SQLite database
  2. Start the APScheduler
  3. Register all aiogram handlers
  4. Start polling
"""

import asyncio
import logging
import socket
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.exceptions import TelegramNetworkError

from config import BOT_TOKEN
from database.db import init_db
from bot.handlers import register_all_handlers
from scheduler.tasks import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set. Check your .env file.")

    # ── Database ──────────────────────────────────────────────────────────────
    await init_db()

    # ── Bot & Dispatcher ──────────────────────────────────────────────────────
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    register_all_handlers(dp)

    # ── Scheduler ─────────────────────────────────────────────────────────────
    scheduler = AsyncIOScheduler(timezone="Africa/Addis_Ababa")
    setup_scheduler(scheduler, bot)
    scheduler.start()
    logger.info("Scheduler started.")

    # ── Polling ───────────────────────────────────────────────────────────────
    logger.info("Bot is starting…")

    async def _check_dns(host: str) -> Optional[str]:
        try:
            # synchronous getaddrinfo in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, socket.getaddrinfo, host, 443)
            return result[0][4][0]
        except Exception:
            return None

    async def _start_polling_with_retries(retries: int = 5) -> None:
        backoff = 5
        for attempt in range(1, retries + 1):
            # quick DNS diagnostic before attempting network call
            ip = await _check_dns("api.telegram.org")
            if not ip:
                logger.warning(
                    "DNS lookup failed for api.telegram.org (attempt %d/%d)."
                    " Check your network, DNS, or proxy settings.",
                    attempt,
                    retries,
                )
            try:
                await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
                return
            except TelegramNetworkError as exc:
                logger.error(
                    "Network error while starting polling (attempt %d/%d): %s",
                    attempt,
                    retries,
                    exc,
                )
            except Exception as exc:  # fallback for unexpected errors
                logger.exception(
                    "Unexpected error while starting polling (attempt %d/%d): %s",
                    attempt,
                    retries,
                    exc,
                )

            if attempt < retries:
                logger.info("Retrying in %d seconds…", backoff)
                await asyncio.sleep(backoff)
                backoff *= 2

        # All retries failed — raise to allow graceful shutdown
        raise RuntimeError("Failed to start polling after multiple attempts.")

    try:
        await _start_polling_with_retries()
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())

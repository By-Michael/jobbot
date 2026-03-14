"""
scraper/telegram_scraper.py — Async Telegram channel scraper using Telethon.

Scrapes channels by numeric ID so both public and private (already-joined)
channels work without needing a public @username.

Two modes:
  1. Keyword search  — scrape posts containing any of the expanded keywords.
  2. Hourly sweep    — scrape the N newest posts from every channel (no filter).
"""

import logging
from typing import Optional

from telethon import TelegramClient
from telethon.errors import ChannelPrivateError, UsernameNotOccupiedError
from telethon.tl.types import Message

from config import (
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_PHONE,
    JOB_CHANNELS,
    POSTS_PER_CHANNEL_SEARCH,
    POSTS_PER_CHANNEL_HOURLY,
)
from database.db import insert_raw_job

logger = logging.getLogger(__name__)

# Shared Telethon client instance (created lazily)
_client: Optional[TelegramClient] = None


async def get_client() -> TelegramClient:
    """Return the authenticated Telethon client, connecting if needed."""
    global _client
    if _client is None:
        _client = TelegramClient("job_bot_session", TELEGRAM_API_ID, TELEGRAM_API_HASH)

    if not _client.is_connected():
        await _client.start(phone=TELEGRAM_PHONE)
        logger.info("Telethon client connected.")

    return _client


def _build_source_link(channel_id: int, message_id: int) -> str:
    """
    Build a t.me link from a numeric channel ID.
    Strip the -100 prefix to get the bare channel ID used in links.
    e.g. -1001193582142 → https://t.me/c/1193582142/42
    """
    bare_id = str(channel_id).lstrip("-").lstrip("100") if str(channel_id).startswith("-100") else str(abs(channel_id))
    # More reliable: remove leading -100
    channel_str = str(channel_id)
    if channel_str.startswith("-100"):
        bare_id = channel_str[4:]  # remove "-100"
    else:
        bare_id = channel_str.lstrip("-")
    return f"https://t.me/c/{bare_id}/{message_id}"


def _message_contains_keywords(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(kw.lower() in lower for kw in keywords)


async def scrape_by_keywords(
    keywords: list[str],
    channels: list[int] = JOB_CHANNELS,
    limit: int = POSTS_PER_CHANNEL_SEARCH,
) -> int:
    """
    Search each channel for posts containing any of the expanded keywords.
    Channels are identified by their numeric Telegram ID.

    Returns the total number of NEW posts inserted into raw_jobs.
    """
    client = await get_client()
    total_new = 0

    for channel_id in channels:
        try:
            entity = await client.get_entity(channel_id)
            channel_name = getattr(entity, "username", None) or str(channel_id)
            inserted = 0

            async for message in client.iter_messages(entity, limit=limit):
                if not isinstance(message, Message) or not message.text:
                    continue
                if not _message_contains_keywords(message.text, keywords):
                    continue

                row_id = await insert_raw_job(
                    channel_name=channel_name,
                    channel_id=channel_id,
                    message_id=message.id,
                    text=message.text,
                    post_date=message.date.isoformat() if message.date else None,
                    source_link=_build_source_link(channel_id, message.id),
                    keyword_used=", ".join(keywords[:3]),
                )
                if row_id:
                    inserted += 1

            logger.info("Channel %s — %d new posts (keyword search)", channel_name, inserted)
            total_new += inserted

        except (ChannelPrivateError, UsernameNotOccupiedError) as exc:
            logger.warning("Skipping channel %s: %s", channel_id, exc)
        except Exception as exc:
            logger.error("Error scraping channel %s: %s", channel_id, exc)

    return total_new


async def scrape_latest(
    channels: list[int] = JOB_CHANNELS,
    limit: int = POSTS_PER_CHANNEL_HOURLY,
) -> int:
    """
    Scrape the newest `limit` posts from every channel without keyword filtering.
    Used by the hourly background scheduler.

    Returns the total number of NEW posts inserted into raw_jobs.
    """
    client = await get_client()
    total_new = 0

    for channel_id in channels:
        try:
            entity = await client.get_entity(channel_id)
            channel_name = getattr(entity, "username", None) or str(channel_id)
            inserted = 0

            async for message in client.iter_messages(entity, limit=limit):
                if not isinstance(message, Message) or not message.text:
                    continue

                row_id = await insert_raw_job(
                    channel_name=channel_name,
                    channel_id=channel_id,
                    message_id=message.id,
                    text=message.text,
                    post_date=message.date.isoformat() if message.date else None,
                    source_link=_build_source_link(channel_id, message.id),
                    keyword_used=None,
                )
                if row_id:
                    inserted += 1

            logger.info("Channel %s — %d new posts (hourly sweep)", channel_name, inserted)
            total_new += inserted

        except (ChannelPrivateError, UsernameNotOccupiedError) as exc:
            logger.warning("Skipping channel %s: %s", channel_id, exc)
        except Exception as exc:
            logger.error("Error scraping channel %s: %s", channel_id, exc)

    return total_new

"""
bot/handlers/help.py — Help and Settings handlers.
"""

from aiogram import F, Router
from aiogram.types import Message

from bot.keyboards import main_menu_keyboard

router = Router()

HELP_TEXT = """
❓ <b>How Job Finder Bot Works</b>

<b>🔍 Search Job</b>
Enter any job title. Our AI automatically expands it into related titles and searches dozens of Ethiopian Telegram job channels for you.

<b>🔔 Notify Me</b>
Subscribe to alerts for any job title. Every hour the bot scrapes new posts and notifies you instantly when a matching job appears.

<b>📅 Today's Jobs</b>
See all job vacancies found in the last 24 hours across all channels — no keyword needed.

<b>💾 Saved Jobs</b>
While browsing results, tap "💾 Save Job" to bookmark a vacancy. Tap "🗑 Unsave" to remove it. Access your saved list here anytime.

<b>⏱ How often are jobs updated?</b>
Every hour. New posts are filtered by AI to remove ads, spam, and expired vacancies.

<b>📅 Ethiopian & Gregorian calendar</b>
The bot understands deadlines in both calendars and automatically marks expired jobs.

<b>📞 Contact Info</b>
Every job must have contact info (Telegram @, email, phone, or link) — jobs without it are automatically discarded.
"""

SETTINGS_TEXT = """
⚙️ <b>Settings</b>

To configure the bot, update the <code>.env</code> file or <code>config.py</code>.

<b>AI Backend (auto-failover):</b>
• <code>GEMINI_API_KEY</code> — Google Gemini 1.5 Flash <b>(primary)</b>
• <code>OPENROUTER_API_KEY</code> — OpenRouter free models <b>(fallback)</b>
• <code>OPENROUTER_MODELS</code> — Fallback model list (comma-separated)

<b>Telegram:</b>
• <code>BOT_TOKEN</code> — Your Telegram bot token
• <code>TELEGRAM_API_ID / HASH</code> — Telethon credentials for scraping
• <code>JOB_CHANNEL_IDS</code> — Numeric channel IDs to scrape

<b>Other:</b>
• <code>DATABASE_PATH</code> — SQLite file location
• <code>POSTS_PER_CHANNEL_SEARCH</code> — Posts fetched per search
• <code>HOURLY_SCRAPE_INTERVAL_MINUTES</code> — Scheduler frequency

Edit <code>config.py</code> to add more job channels.
"""


@router.message(F.text == "❓ Help")
async def help_handler(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard())


@router.message(F.text == "⚙️ Settings")
async def settings_handler(message: Message) -> None:
    await message.answer(SETTINGS_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard())

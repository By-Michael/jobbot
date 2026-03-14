"""
config.py — Central configuration for the Job Bot.
All settings are loaded from environment variables via .env
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram Bot ─────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ─── Telethon (User API — for scraping private/public channels) ───────────────
TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE: str = os.getenv("TELEGRAM_PHONE", "")

# ─── Gemini AI (PRIMARY) ──────────────────────────────────────────────────────
# Model: gemini-1.5-flash — fastest and most reliable for general tasks.
GEMINI_API_KEY: str = os.getenv(
    "GEMINI_API_KEY",
    "AIzaSyCqi8nKm2f32MWG14q2cUpBHUetjSCb8ME",
)

# ─── OpenRouter AI (FALLBACK) ─────────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv(
    "OPENROUTER_API_KEY",
    "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",
)

# Free models tried in order when Gemini is unavailable
_models_env = os.getenv("OPENROUTER_MODELS", "")
OPENROUTER_MODELS: list[str] = (
    [m.strip() for m in _models_env.split(",") if m.strip()]
    if _models_env
    else [
        "meta-llama/llama-3.3-70b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        "google/gemma-3-27b-it:free",
        "qwen/qwen-2-7b-instruct:free",
    ]
)

# ─── Database ─────────────────────────────────────────────────────────────────
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "job_bot.db")

# ─── Telegram Job Channels to Scrape (numeric IDs) ───────────────────────────
_channels_env = os.getenv("JOB_CHANNEL_IDS", "")
JOB_CHANNELS: list[int] = (
    [int(c.strip()) for c in _channels_env.split(",") if c.strip()]
    if _channels_env
    else [
        -1001193582142,
        -1001197229252,
        -1001140766931,
    ]
)

# ─── Scraping Settings ────────────────────────────────────────────────────────
POSTS_PER_CHANNEL_SEARCH: int = int(os.getenv("POSTS_PER_CHANNEL_SEARCH", "100"))
POSTS_PER_CHANNEL_HOURLY: int = int(os.getenv("POSTS_PER_CHANNEL_HOURLY", "50"))

# ─── Pagination ───────────────────────────────────────────────────────────────
JOBS_PER_PAGE: int = int(os.getenv("JOBS_PER_PAGE", "10"))

# ─── Scheduler ────────────────────────────────────────────────────────────────
HOURLY_SCRAPE_INTERVAL_MINUTES: int = int(os.getenv("HOURLY_SCRAPE_INTERVAL_MINUTES", "60"))
EXPIRY_CHECK_INTERVAL_MINUTES: int = int(os.getenv("EXPIRY_CHECK_INTERVAL_MINUTES", "60"))

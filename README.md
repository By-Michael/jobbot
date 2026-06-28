# JobBot

A Telegram bot that scrapes job postings from Telegram channels, filters them with AI, and notifies you when relevant jobs appear.

## What it does

- Scrapes job posts from configured Telegram channels
- Uses AI (Gemini, with OpenRouter as fallback) to filter out non-job posts and extract structured info
- Lets users search for jobs by title, with AI-expanded keywords
- Sends hourly alerts for saved job searches
- Lets users save jobs and view them later

## Requirements

- Python 3.10+
- A Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Telegram API ID & Hash (from [my.telegram.org](https://my.telegram.org)) — needed for channel scraping
- A Gemini API key (free at [aistudio.google.com](https://aistudio.google.com))
- Optionally, an OpenRouter API key (free tier available) as AI fallback

## Setup

1. **Clone the repo and install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   Then fill in your `.env`:
   ```
   BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_API_ID=your_api_id
   TELEGRAM_API_HASH=your_api_hash
   TELEGRAM_PHONE=+1234567890

   GEMINI_API_KEY=your_gemini_key
   OPENROUTER_API_KEY=your_openrouter_key   # optional fallback

   JOB_CHANNEL_IDS=-1001234567890,-1009876543210  # channels to scrape
   ```

3. **Run the bot**
   ```bash
   python main.py
   ```
   On first run, Telethon will ask you to log in with your phone number to authorize channel scraping.

## Project structure

```
jobbot-main/
├── main.py              # Entry point
├── config.py            # Loads settings from .env
├── ai/                  # AI clients and logic
│   ├── gemini_client.py
│   ├── openrouter_client.py
│   ├── job_filter.py    # Decides if a post is a real job
│   ├── job_organizer.py # Extracts title, company, deadline, etc.
│   └── keyword_expander.py
├── bot/
│   ├── handlers/        # Bot command and button handlers
│   └── keyboards.py
├── database/
│   └── db.py            # SQLite via aiosqlite
├── scheduler/
│   └── tasks.py         # Hourly scrape + user notifications
└── scraper/
    └── telegram_scraper.py
```

## Bot commands / menu

| Button | What it does |
|--------|-------------|
| 🔍 Search Job | Search by job title (AI expands your keywords) |
| 🔔 Notify Me | Get alerts when new matching jobs are posted |
| 📌 Saved Jobs | View jobs you've bookmarked |
| 📅 Today's Jobs | See jobs posted today |
| ❓ Help | Usage instructions |

## Configuration options

All settings can be set in `.env`. Key ones:

| Variable | Default | Description |
|----------|---------|-------------|
| `JOB_CHANNEL_IDS` | 3 preset channels | Telegram channel IDs to scrape |
| `POSTS_PER_CHANNEL_SEARCH` | 100 | Posts to fetch on manual search |
| `POSTS_PER_CHANNEL_HOURLY` | 50 | Posts to fetch on scheduled runs |
| `HOURLY_SCRAPE_INTERVAL_MINUTES` | 60 | How often to auto-scrape |
| `DATABASE_PATH` | `job_bot.db` | SQLite database file location |

## Notes

- The bot uses SQLite — no external database needed.
- Gemini is used first for AI tasks; OpenRouter free models are the fallback if Gemini fails.
- The scheduler timezone is set to `Africa/Addis_Ababa` in `main.py` — change it if needed.

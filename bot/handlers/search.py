"""
bot/handlers/search.py — Smart job search with AI keyword expansion and pagination.

Flow:
  1. User presses "Search Job"
  2. Bot asks for a job title
  3. AI expands keywords  (Gemini → OpenRouter fallback)
  4. Scraper searches Telegram channels
  5. Results stored in FSM state and paginated
"""

import asyncio
import logging
from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ai.keyword_expander import expand_keywords
from bot.formatters import format_job_card, paginate
from bot.keyboards import (
    cancel_keyboard,
    job_pagination_keyboard,
    main_menu_keyboard,
)
from database.db import search_organized_jobs
from database.db import (
    get_unfiltered_raw_jobs,
    insert_filtered_job,
    insert_organized_job,
    get_valid_unorganized_filtered_jobs,
)
from ai.job_filter import batch_filter_jobs
from ai.job_organizer import batch_organize_jobs

logger = logging.getLogger(__name__)
router = Router()

# ─── Try to import the live scraper; fall back gracefully ─────────────────────
try:
    from scraper.telegram_scraper import scrape_by_keywords as _scrape
    _HAS_SCRAPER = True
except ImportError:
    _HAS_SCRAPER = False
    logger.warning("scraper.telegram_scraper not found — search will use cached DB results only.")


class SearchState(StatesGroup):
    waiting_for_keyword = State()


# ─── Trigger ──────────────────────────────────────────────────────────────────

@router.message(F.text == "🔍 Search Job")
async def search_start(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchState.waiting_for_keyword)
    await message.answer(
        "🔍 <b>Job Search</b>\n\n"
        "Enter the job title you are looking for.\n"
        "<i>Example: Software Engineer</i>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


@router.message(SearchState.waiting_for_keyword, F.text == "❌ Cancel")
async def search_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Search cancelled.", reply_markup=main_menu_keyboard())


# ─── Keyword received ─────────────────────────────────────────────────────────

@router.message(SearchState.waiting_for_keyword)
async def search_keyword_received(message: Message, state: FSMContext) -> None:
    keyword = message.text.strip()
    await state.clear()

    status_msg = await message.answer(
        f"🤖 <b>Expanding keywords for:</b> <i>{keyword}</i>…",
        parse_mode="HTML",
    )

    # 1. AI keyword expansion
    try:
        expanded = await expand_keywords(keyword)
    except Exception as exc:
        logger.error("Keyword expansion error: %s", exc)
        expanded = [keyword]

    await status_msg.edit_text(
        "🔍 <b>Searching with:</b>\n" + "\n".join(f"• {k}" for k in expanded),
        parse_mode="HTML",
    )

    # 2. Scrape channels (if scraper is available)
    if _HAS_SCRAPER:
        try:
            new_posts = await _scrape(expanded)
            await status_msg.edit_text(
                f"⚙️ Found <b>{new_posts}</b> new posts. Running AI filter…",
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.error("Scraping error: %s", exc)
            await status_msg.edit_text("⚠️ Scraping failed. Showing cached results.")

    # 3. Filter & organise any unprocessed raw jobs
    await _run_pipeline(status_msg)

    # 4. Retrieve matching organised jobs from DB
    jobs = await search_organized_jobs(expanded)

    if not jobs:
        try:
            await status_msg.delete()
        except Exception:
            pass
        await message.answer(
            "😕 No matching jobs found right now.\n"
            "Press <b>🔔 Notify Me</b> to be alerted when new ones appear.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
        return

    # BUG FIX #1: store jobs in FSM state so pagination callbacks can access them
    await state.update_data(search_jobs=jobs, search_keyword=keyword)

    # 5. Show page 0
    await _show_jobs_page(
        message=message,
        jobs=jobs,
        page=0,
        context="search",
        status_msg=status_msg,
        keyword=keyword,
    )


async def _run_pipeline(status_msg: Message | None = None) -> None:
    """Run the AI filter → organiser pipeline for all pending raw jobs."""
    today = date.today().strftime("%Y-%m-%d")

    # Filter
    unfiltered = await get_unfiltered_raw_jobs()
    if unfiltered:
        pairs = await batch_filter_jobs(unfiltered, today)
        for raw_job, result in pairs:
            await insert_filtered_job(
                raw_job_id=raw_job["id"],
                is_valid_job=result["is_valid_job"],
                deadline=result["deadline"],
                is_expired=result["is_expired"],
                contact_info=result["contact_info"],
                validation_notes=result["validation_notes"],
            )

    # Organise
    valid_jobs = await get_valid_unorganized_filtered_jobs()
    if valid_jobs:
        if status_msg:
            try:
                await status_msg.edit_text(
                    f"🗂 Organising <b>{len(valid_jobs)}</b> valid jobs…",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        org_pairs = await batch_organize_jobs(valid_jobs)
        for filtered_job, org in org_pairs:
            await insert_organized_job(
                filtered_job_id=filtered_job["id"],
                title=org["title"],
                company=org["company"],
                description=org["description"],
                location=org["location"],
                payment=org["payment"],
                deadline=org["deadline"],
                contact=org["contact"],
                source=filtered_job.get("channel_name"),
                source_link=filtered_job.get("source_link"),
            )


async def _show_jobs_page(
    message: Message,
    jobs: list[dict],
    page: int,
    context: str,
    status_msg=None,
    keyword: str = "",
) -> None:
    page_jobs, _ = paginate(jobs, page, per_page=1)

    if not page_jobs:
        return

    job = page_jobs[0]
    text = format_job_card(job)
    if keyword:
        text = f"🔍 Results for <b>{keyword}</b> — {len(jobs)} jobs found\n\n" + text

    keyboard = job_pagination_keyboard(
        page=page,
        total_pages=len(jobs),  # one job per page
        job_id=job["id"],
        context=context,
    )

    if status_msg:
        try:
            await status_msg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            return
        except Exception:
            pass

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


# ─── Pagination callback ───────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("page:search:"))
async def cb_search_page(callback: CallbackQuery, state: FSMContext) -> None:
    page = int(callback.data.split(":")[2])

    # BUG FIX #1: jobs are now reliably stored in FSM state after a search
    data = await state.get_data()
    jobs = data.get("search_jobs", [])
    keyword = data.get("search_keyword", "")

    if not jobs:
        await callback.answer(
            "⚠️ Session expired. Please run a new search.", show_alert=True
        )
        return

    page_items, _ = paginate(jobs, page, per_page=1)
    if not page_items:
        await callback.answer()
        return

    job = page_items[0]
    text = f"🔍 Results for <b>{keyword}</b> — {len(jobs)} jobs found\n\n" if keyword else ""
    text += format_job_card(job)
    keyboard = job_pagination_keyboard(page, len(jobs), job["id"], "search")

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


# ─── Save job callback ─────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("save_job:"))
async def cb_save_job(callback: CallbackQuery) -> None:
    from database.db import save_job
    job_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    # BUG FIX #4: save_job now correctly returns False on duplicate
    success = await save_job(user_id, job_id)
    await callback.answer(
        "✅ Job saved!" if success else "📌 Already in your saved list.",
        show_alert=False,
    )


# expose pipeline for scheduler
run_pipeline = _run_pipeline

"""
bot/handlers/today.py — "Today's Jobs" feature.
Shows jobs scraped in the last 24 hours, paginated.
"""

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.formatters import format_job_card, paginate
from bot.keyboards import job_pagination_keyboard, main_menu_keyboard
from database.db import get_todays_jobs

router = Router()


@router.message(F.text == "📅 Today's Jobs")
async def today_jobs(message: Message) -> None:
    jobs = await get_todays_jobs()

    if not jobs:
        await message.answer(
            "📭 No new jobs in the last 24 hours.\n\n"
            "Try again later or set up a <b>🔔 Notification</b> to be alerted automatically.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
        return

    await _show_page(message, jobs, page=0)


async def _show_page(
    message: Message,
    jobs: list[dict],
    page: int,
    edit: bool = False,
) -> None:
    page_items, _ = paginate(jobs, page, per_page=1)
    if not page_items:
        return

    job = page_items[0]
    text = (
        f"📅 <b>Today's Jobs</b> — {len(jobs)} available\n\n"
        + format_job_card(job)
    )
    keyboard = job_pagination_keyboard(page, len(jobs), job["id"], "today")

    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(lambda c: c.data and c.data.startswith("page:today:"))
async def cb_today_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[2])
    # Re-fetch from DB so we always have a fresh list without needing FSM state
    jobs = await get_todays_jobs()

    if not jobs:
        await callback.answer("No jobs available.", show_alert=True)
        return

    page_items, _ = paginate(jobs, page, per_page=1)
    if not page_items:
        await callback.answer()
        return

    job = page_items[0]
    text = f"📅 <b>Today's Jobs</b> — {len(jobs)} available\n\n" + format_job_card(job)
    keyboard = job_pagination_keyboard(page, len(jobs), job["id"], "today")

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

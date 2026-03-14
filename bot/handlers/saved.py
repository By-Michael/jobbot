"""
bot/handlers/saved.py — Saved jobs feature.
"""

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.formatters import format_job_card, paginate
from bot.keyboards import job_pagination_keyboard, main_menu_keyboard
from database.db import get_saved_jobs, unsave_job

router = Router()


@router.message(F.text == "💾 Saved Jobs")
async def saved_jobs(message: Message) -> None:
    jobs = await get_saved_jobs(message.from_user.id)

    if not jobs:
        await message.answer(
            "💾 You haven't saved any jobs yet.\n\n"
            "While browsing results, tap <b>💾 Save Job</b> to bookmark them here.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
        return

    await _show_page(message, jobs, page=0)


async def _show_page(message: Message, jobs: list[dict], page: int, edit: bool = False) -> None:
    page_items, _ = paginate(jobs, page, per_page=1)
    if not page_items:
        return

    job = page_items[0]
    text = f"💾 <b>Saved Jobs</b> — {len(jobs)} saved\n\n" + format_job_card(job)
    keyboard = job_pagination_keyboard(page, len(jobs), job["id"], "saved")

    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(lambda c: c.data and c.data.startswith("page:saved:"))
async def cb_saved_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[2])
    jobs = await get_saved_jobs(callback.from_user.id)

    if not jobs:
        await callback.answer("No saved jobs.", show_alert=True)
        return

    page_items, _ = paginate(jobs, page, per_page=1)
    if not page_items:
        await callback.answer()
        return

    job = page_items[0]
    text = f"💾 <b>Saved Jobs</b> — {len(jobs)} saved\n\n" + format_job_card(job)
    keyboard = job_pagination_keyboard(page, len(jobs), job["id"], "saved")

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


# BUG FIX #5: handle the "Unsave" button that appears in the saved-jobs context
@router.callback_query(lambda c: c.data and c.data.startswith("unsave_job:"))
async def cb_unsave_job(callback: CallbackQuery) -> None:
    job_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    await unsave_job(user_id, job_id)
    await callback.answer("🗑 Job removed from saved list.", show_alert=False)

    # Refresh saved list; show updated page or return to menu if empty
    jobs = await get_saved_jobs(user_id)
    if not jobs:
        await callback.message.edit_text(
            "💾 Your saved list is now empty.\n\n"
            "Browse <b>🔍 Search Job</b> or <b>📅 Today's Jobs</b> to find more.",
            parse_mode="HTML",
        )
        await callback.message.answer("Main Menu", reply_markup=main_menu_keyboard())
    else:
        # Stay on same page index (or last page if we removed the last item on this page)
        page = 0  # reset to first page after removal for simplicity
        page_items, _ = paginate(jobs, page, per_page=1)
        if page_items:
            job = page_items[0]
            text = f"💾 <b>Saved Jobs</b> — {len(jobs)} saved\n\n" + format_job_card(job)
            keyboard = job_pagination_keyboard(page, len(jobs), job["id"], "saved")
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

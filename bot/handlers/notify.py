"""
bot/handlers/notify.py — Notification management.

Users can subscribe to job alerts for specific keywords.
When new matching jobs are found by the scheduler, they are notified.
"""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ai.keyword_expander import expand_keywords
from bot.keyboards import (
    cancel_keyboard,
    main_menu_keyboard,
    notification_list_keyboard,
)
from database.db import (
    add_notification,
    disable_notification,
    get_user_notifications,
    upsert_user,
)

logger = logging.getLogger(__name__)
router = Router()


class NotifyState(StatesGroup):
    waiting_for_keyword = State()


# ─── Main "Notify Me" button ──────────────────────────────────────────────────

@router.message(F.text == "🔔 Notify Me")
async def notify_start(message: Message, state: FSMContext) -> None:
    await upsert_user(message.from_user.id, message.from_user.username)
    notifications = await get_user_notifications(message.from_user.id)

    if notifications:
        await message.answer(
            "🔔 <b>Your Active Notifications</b>\n\n"
            "You'll be alerted when matching jobs are found.",
            parse_mode="HTML",
            reply_markup=notification_list_keyboard(notifications),
        )
    else:
        await _ask_for_keyword(message, state)


# ─── Inline "Notify Me" from search results ───────────────────────────────────

@router.callback_query(lambda c: c.data == "notify_from_search")
async def cb_notify_from_search(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    # BUG FIX #6: always pass state so FSM is properly set regardless of path
    await state.set_state(NotifyState.waiting_for_keyword)
    await callback.message.answer(
        "🔔 <b>Set Job Alert</b>\n\nEnter the job title you want to be notified about:\n"
        "<i>Example: Data Analyst</i>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


@router.callback_query(lambda c: c.data == "add_notification")
async def cb_add_notification(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(NotifyState.waiting_for_keyword)
    await callback.message.answer(
        "🔔 <b>Set Job Alert</b>\n\nEnter the job title you want to be notified about:\n"
        "<i>Example: Data Analyst</i>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


async def _ask_for_keyword(message: Message, state: FSMContext | None = None) -> None:
    if state:
        await state.set_state(NotifyState.waiting_for_keyword)
    await message.answer(
        "🔔 <b>Set Job Alert</b>\n\nEnter the job title you want to be notified about:\n"
        "<i>Example: Data Analyst</i>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


# ─── FSM: receive keyword ─────────────────────────────────────────────────────

@router.message(NotifyState.waiting_for_keyword, F.text == "❌ Cancel")
async def notify_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Cancelled.", reply_markup=main_menu_keyboard())


@router.message(NotifyState.waiting_for_keyword)
async def notify_keyword_received(message: Message, state: FSMContext) -> None:
    keyword = message.text.strip()
    await state.clear()

    status = await message.answer(
        f"🤖 Expanding keywords for <i>{keyword}</i>…", parse_mode="HTML"
    )

    try:
        expanded = await expand_keywords(keyword)
    except Exception as exc:
        logger.error("Keyword expansion error: %s", exc)
        expanded = [keyword]

    await add_notification(
        user_id=message.from_user.id,
        keyword=keyword,
        expanded_keywords=expanded,
    )

    kw_list = "\n".join(f"• {k}" for k in expanded)
    await status.edit_text(
        f"✅ <b>Notification Set!</b>\n\n"
        f"You'll be alerted for:\n{kw_list}\n\n"
        f"Jobs are checked every hour.",
        parse_mode="HTML",
    )
    # Send a separate message to restore the reply keyboard (can't mix with edit_text)
    await message.answer("Use the menu to continue.", reply_markup=main_menu_keyboard())


# ─── Remove notification ──────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("remove_notif:"))
async def cb_remove_notification(callback: CallbackQuery) -> None:
    notif_id = int(callback.data.split(":")[1])
    await disable_notification(notif_id)
    await callback.answer("🗑 Notification removed.", show_alert=False)

    # Refresh the list
    notifications = await get_user_notifications(callback.from_user.id)
    if notifications:
        await callback.message.edit_reply_markup(
            reply_markup=notification_list_keyboard(notifications)
        )
    else:
        # BUG FIX #3: can't use ReplyKeyboardMarkup in edit_text — send a new message instead
        await callback.message.edit_text(
            "✅ All notifications removed.\n\nUse the menu below to set new ones.",
        )
        await callback.message.answer(
            "You have no active notifications.",
            reply_markup=main_menu_keyboard(),
        )

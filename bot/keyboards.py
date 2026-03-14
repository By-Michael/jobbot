"""
bot/keyboards.py — All inline and reply keyboards for the bot.
"""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ─── Main Menu ────────────────────────────────────────────────────────────────

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🔍 Search Job"), KeyboardButton(text="🔔 Notify Me"))
    builder.row(KeyboardButton(text="📅 Today's Jobs"), KeyboardButton(text="💾 Saved Jobs"))
    builder.row(KeyboardButton(text="❓ Help"), KeyboardButton(text="⚙️ Settings"))
    return builder.as_markup(resize_keyboard=True)


# ─── Job Pagination ───────────────────────────────────────────────────────────

def job_pagination_keyboard(
    page: int,
    total_pages: int,
    job_id: int,
    context: str = "search",
) -> InlineKeyboardMarkup:
    """
    Build navigation + action inline keyboard for job result pages.

    Parameters
    ----------
    page        : Current page (0-indexed).
    total_pages : Total number of pages.
    job_id      : ID of the currently displayed organised job.
    context     : 'search' | 'today' | 'saved' — used in callback data.
    """
    builder = InlineKeyboardBuilder()

    # Navigation row
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅ Prev", callback_data=f"page:{context}:{page - 1}")
        )
    nav_buttons.append(
        # BUG FIX #2: was "noop" with no handler — now uses a proper callback prefix
        InlineKeyboardButton(
            text=f"📄 {page + 1}/{total_pages}",
            callback_data="page_indicator",
        )
    )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="Next ➡", callback_data=f"page:{context}:{page + 1}")
        )
    builder.row(*nav_buttons)

    # Action row — BUG FIX #5: show context-appropriate action buttons
    if context == "saved":
        # When viewing saved jobs show Unsave instead of Save
        builder.row(
            InlineKeyboardButton(text="🔔 Notify Me", callback_data="notify_from_search"),
            InlineKeyboardButton(text="🗑 Unsave", callback_data=f"unsave_job:{job_id}"),
        )
    else:
        builder.row(
            InlineKeyboardButton(text="🔔 Notify Me", callback_data="notify_from_search"),
            InlineKeyboardButton(text="💾 Save Job", callback_data=f"save_job:{job_id}"),
        )

    return builder.as_markup()


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    return builder.as_markup()


def cancel_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="❌ Cancel"))
    return builder.as_markup(resize_keyboard=True)


def notification_list_keyboard(notifications: list[dict]) -> InlineKeyboardMarkup:
    """Show active notifications with a disable button for each."""
    builder = InlineKeyboardBuilder()
    for notif in notifications:
        builder.row(
            InlineKeyboardButton(
                text=f"🔔 {notif['keyword']}",
                callback_data="page_indicator",  # non-functional info button
            ),
            InlineKeyboardButton(
                text="🗑 Remove",
                callback_data=f"remove_notif:{notif['id']}",
            ),
        )
    builder.row(InlineKeyboardButton(text="➕ Add New", callback_data="add_notification"))
    return builder.as_markup()

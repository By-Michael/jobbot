"""
bot/handlers/start.py — /start command and main menu navigation.
"""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from bot.keyboards import main_menu_keyboard
from database.db import upsert_user

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await upsert_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "👋 <b>Welcome to Job Finder Bot!</b>\n\n"
        "I help you discover job opportunities posted in Ethiopian Telegram channels.\n\n"
        "Use the menu below to get started:",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(lambda c: c.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery) -> None:
    """Return to main menu from any inline keyboard."""
    # Edit the current message away so the inline keyboard disappears cleanly,
    # then send a fresh reply-keyboard message.
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("🏠 Main Menu", reply_markup=main_menu_keyboard())
    await callback.answer()


# BUG FIX #2: Handle the page-indicator and legacy "noop" buttons so Telegram
# doesn't show a spinning loader when the user taps them.
@router.callback_query(lambda c: c.data in ("page_indicator", "noop"))
async def cb_noop(callback: CallbackQuery) -> None:
    """Silent answer for display-only buttons (page counter, keyword labels)."""
    await callback.answer()

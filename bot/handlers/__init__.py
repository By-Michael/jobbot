from aiogram import Router

from bot.handlers import start, search, notify, today, saved, help

def register_all_handlers(dp) -> None:
    """Register all handler routers with the dispatcher."""
    for module in [start, search, notify, today, saved, help]:
        dp.include_router(module.router)

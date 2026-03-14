"""
bot/formatters.py — Telegram message formatting utilities.
"""

from config import JOBS_PER_PAGE


def format_job_card(job: dict, index: int | None = None) -> str:
    """
    Format a single organised job into a Telegram-ready HTML message.
    """
    title = job.get("title") or "Unknown Position"
    company = job.get("company") or "Unknown Company"
    location = job.get("location") or "Not specified"
    description = job.get("description") or ""
    payment = job.get("payment")
    deadline = job.get("deadline") or "Not specified"
    contact = job.get("contact") or "See source"
    source_link = job.get("source_link") or ""

    header = f"<b>#{index} {title}</b>" if index is not None else f"<b>{title}</b>"

    lines = [
        header,
        f"🏢 <b>Company:</b> {company}",
        f"📍 <b>Location:</b> {location}",
    ]

    if description:
        lines.append(f"\n📝 {description}")

    if payment:
        lines.append(f"💰 <b>Payment:</b> {payment}")

    lines += [
        f"⏰ <b>Deadline:</b> {deadline}",
        f"📞 <b>Contact:</b> {contact}",
    ]

    if source_link:
        lines.append(f"\n🔗 <a href='{source_link}'>View Original Post</a>")

    return "\n".join(lines)


def paginate(items: list, page: int, per_page: int = JOBS_PER_PAGE) -> tuple[list, int]:
    """
    Return the items for a given page and the total page count.

    Returns
    -------
    (page_items, total_pages)
    """
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    return items[start : start + per_page], total_pages

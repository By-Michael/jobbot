"""
scheduler/tasks.py — APScheduler background tasks.

Tasks:
  1. hourly_scrape    — scrape latest posts + run AI pipeline
  2. check_expiry     — mark jobs whose deadlines have passed
  3. notify_users     — match newly organised jobs to user notification subscriptions
"""

import logging
from datetime import date, datetime

from aiogram import Bot

from config import HOURLY_SCRAPE_INTERVAL_MINUTES, EXPIRY_CHECK_INTERVAL_MINUTES
from database.db import (
    get_all_active_organized_jobs,
    get_active_notifications,
    get_unfiltered_raw_jobs,
    get_valid_unorganized_filtered_jobs,
    insert_filtered_job,
    insert_organized_job,
    mark_job_expired,
)
from scraper.telegram_scraper import scrape_latest
from ai.job_filter import batch_filter_jobs
from ai.job_organizer import batch_organize_jobs

logger = logging.getLogger(__name__)


async def hourly_scrape(bot: Bot) -> None:
    """
    1. Scrape the latest posts from all channels.
    2. Run AI filter on new raw jobs.
    3. Organise valid filtered jobs.
    4. Match new organised jobs to notification subscriptions and alert users.
    """
    logger.info("⏱ Hourly scrape started.")
    today = date.today().strftime("%Y-%m-%d")

    # Step 1 — Scrape
    try:
        new_raw = await scrape_latest()
        logger.info("Scraped %d new raw posts.", new_raw)
    except Exception as exc:
        logger.error("Scrape error: %s", exc)
        return

    # Step 2 — Filter
    unfiltered = await get_unfiltered_raw_jobs()
    filtered_ids = []
    if unfiltered:
        pairs = await batch_filter_jobs(unfiltered, today)
        for raw_job, result in pairs:
            fid = await insert_filtered_job(
                raw_job_id=raw_job["id"],
                is_valid_job=result["is_valid_job"],
                deadline=result["deadline"],
                is_expired=result["is_expired"],
                contact_info=result["contact_info"],
                validation_notes=result["validation_notes"],
            )
            if result["is_valid_job"] and fid:
                filtered_ids.append(fid)
        logger.info("Filtered %d posts → %d valid.", len(unfiltered), len(filtered_ids))

    # Step 3 — Organise
    valid_jobs = await get_valid_unorganized_filtered_jobs()
    new_organized: list[dict] = []
    if valid_jobs:
        org_pairs = await batch_organize_jobs(valid_jobs)
        for filtered_job, org in org_pairs:
            oid = await insert_organized_job(
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
            if oid:
                new_organized.append({**org, "id": oid, "source_link": filtered_job.get("source_link")})
        logger.info("Organised %d new jobs.", len(new_organized))

    # Step 4 — Notify users
    if new_organized:
        await notify_users(bot, new_organized)

    logger.info("⏱ Hourly scrape complete.")


async def check_expiry() -> None:
    """Mark organised jobs whose deadlines have passed as expired."""
    today = date.today()
    jobs = await get_all_active_organized_jobs()
    expired_count = 0

    for job in jobs:
        deadline_str = job.get("deadline")
        if not deadline_str:
            continue
        try:
            deadline = date.fromisoformat(deadline_str)
            if deadline < today:
                await mark_job_expired(job["id"])
                expired_count += 1
        except ValueError:
            continue

    if expired_count:
        logger.info("Expired %d jobs.", expired_count)


async def notify_users(bot: Bot, new_jobs: list[dict]) -> None:
    """
    Match new organised jobs against all active notification subscriptions
    and send alerts to users with matching keywords.
    """
    subscriptions = await get_active_notifications()
    if not subscriptions:
        return

    for job in new_jobs:
        title_lower = (job.get("title") or "").lower()
        description_lower = (job.get("description") or "").lower()

        for sub in subscriptions:
            keywords: list[str] = sub.get("expanded_keywords", [])
            matched = any(
                kw.lower() in title_lower or kw.lower() in description_lower
                for kw in keywords
            )
            if not matched:
                continue

            # Build notification message
            source_link = job.get("source_link") or ""
            deadline = job.get("deadline") or "Not specified"
            contact = job.get("contact") or "See source"
            company = job.get("company") or ""

            text = (
                "🔔 <b>New Job Found!</b>\n\n"
                f"<b>{job.get('title', 'Position')}</b>"
                + (f" — {company}" if company else "")
                + f"\n⏰ Deadline: {deadline}"
                + f"\n📞 Contact: {contact}"
            )
            if source_link:
                text += f"\n\n🔗 <a href='{source_link}'>View Original Post</a>"

            try:
                await bot.send_message(
                    sub["user_id"],
                    text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except Exception as exc:
                logger.warning("Could not notify user %s: %s", sub["user_id"], exc)


def setup_scheduler(scheduler, bot: Bot) -> None:
    """Register all tasks with the APScheduler instance."""
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler.add_job(
        hourly_scrape,
        trigger=IntervalTrigger(minutes=HOURLY_SCRAPE_INTERVAL_MINUTES),
        kwargs={"bot": bot},
        id="hourly_scrape",
        replace_existing=True,
        misfire_grace_time=120,
    )

    scheduler.add_job(
        check_expiry,
        trigger=IntervalTrigger(minutes=EXPIRY_CHECK_INTERVAL_MINUTES),
        id="check_expiry",
        replace_existing=True,
        misfire_grace_time=120,
    )

    logger.info("Scheduler jobs registered.")

"""
ai/job_filter.py — AI-powered job validation.

Evaluates raw Telegram posts and decides whether each is a real job posting,
extracts the deadline (handling Ethiopian calendar), and checks contact info.
"""

import json
import logging
import re
from typing import TypedDict

from ai.openrouter_client import ask_openrouter as ask_poe

logger = logging.getLogger(__name__)


class FilterResult(TypedDict):
    is_valid_job: bool
    deadline: str | None
    is_expired: bool
    contact_info: str | None
    validation_notes: str


_FILTER_PROMPT = """\
You are a job posting validator for an Ethiopian job board Telegram bot.

Analyse the following Telegram post and return a JSON object with these exact fields:

{{
  "is_valid_job": true | false,
  "deadline": "YYYY-MM-DD" | null,
  "is_expired": true | false,
  "contact_info": "extracted contact string" | null,
  "validation_notes": "short reason"
}}

Rules:
1. is_valid_job must be false if the post is: an advertisement, training/course announcement,
   event invitation, irrelevant content, spam, or does not describe a real job vacancy.
2. deadline: extract any application deadline. Convert Ethiopian calendar dates to Gregorian (YYYY-MM-DD).
   If no deadline is found, return null.
3. is_expired: set true if the deadline has already passed relative to today ({today}).
   If no deadline, set false.
4. contact_info: extract any Telegram @username, phone number, email address, website URL,
   or application link. If none exists, return null. is_valid_job must be false when contact_info is null.
5. Return ONLY the raw JSON object. No markdown, no explanation.

Post text:
\"\"\"
{text}
\"\"\"
"""


async def filter_job(raw_text: str, today: str) -> FilterResult:
    """
    Run a single raw post through the AI filter.

    Parameters
    ----------
    raw_text : The scraped Telegram message text.
    today    : Today's date as YYYY-MM-DD (used for expiry checks).

    Returns
    -------
    A FilterResult dict.
    """
    prompt = _FILTER_PROMPT.format(text=raw_text[:3000], today=today)

    try:
        raw = await ask_poe(prompt)
        # Strip possible markdown code fences
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        data = json.loads(raw)
        return FilterResult(
            is_valid_job=bool(data.get("is_valid_job", False)),
            deadline=data.get("deadline"),
            is_expired=bool(data.get("is_expired", False)),
            contact_info=data.get("contact_info"),
            validation_notes=str(data.get("validation_notes", "")),
        )
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("filter_job parse error (%s) — raw=%r", exc, raw if 'raw' in dir() else "")
        return FilterResult(
            is_valid_job=False,
            deadline=None,
            is_expired=False,
            contact_info=None,
            validation_notes=f"Parse error: {exc}",
        )
    except Exception as exc:
        logger.error("filter_job AI error: %s", exc)
        return FilterResult(
            is_valid_job=False,
            deadline=None,
            is_expired=False,
            contact_info=None,
            validation_notes=f"AI error: {exc}",
        )


async def batch_filter_jobs(
    raw_jobs: list[dict], today: str
) -> list[tuple[dict, FilterResult]]:
    """
    Process a list of raw job dicts concurrently (up to 5 at a time).
    Returns a list of (raw_job, filter_result) pairs.
    """
    import asyncio

    semaphore = asyncio.Semaphore(5)

    async def _process(job: dict) -> tuple[dict, FilterResult]:
        async with semaphore:
            result = await filter_job(job["text"], today)
            return job, result

    tasks = [_process(j) for j in raw_jobs]
    return await asyncio.gather(*tasks)

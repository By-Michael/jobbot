"""
ai/job_organizer.py — AI-powered job post structuring.

Converts messy Telegram text into a clean, structured job record.
"""

import json
import logging
import re
from typing import TypedDict

from ai.openrouter_client import ask_openrouter as ask_poe

logger = logging.getLogger(__name__)


class OrganizedJob(TypedDict):
    title: str
    company: str | None
    description: str | None
    location: str | None
    payment: str | None
    deadline: str | None
    contact: str | None


_ORGANIZE_PROMPT = """\
You are a structured data extractor for a job board bot.

Convert the following raw Telegram job post into a clean JSON object with these exact fields:

{{
  "title": "Job title",
  "company": "Company or organisation name, or null",
  "description": "A clean 2-3 sentence summary of the role and requirements",
  "location": "City/country or 'Remote', or null",
  "payment": "Salary or compensation if mentioned, or null",
  "deadline": "Application deadline as YYYY-MM-DD, or null",
  "contact": "All contact info (Telegram @, email, phone, URL) combined in one string"
}}

Rules:
- Use clear, professional English.
- description must be concise (max 3 sentences).
- If a field cannot be determined, use null.
- Return ONLY the raw JSON object. No markdown, no explanation.

Raw post:
\"\"\"
{text}
\"\"\"
"""


async def organize_job(raw_text: str, contact_info: str | None = None) -> OrganizedJob:
    """
    Organise a single validated job post into a structured record.
    """
    prompt = _ORGANIZE_PROMPT.format(text=raw_text[:3000])

    try:
        raw = await ask_poe(prompt)
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        data = json.loads(raw)

        # Fall back to AI-extracted contact if organiser found none
        contact = data.get("contact") or contact_info

        return OrganizedJob(
            title=str(data.get("title") or "Untitled Position"),
            company=data.get("company"),
            description=data.get("description"),
            location=data.get("location"),
            payment=data.get("payment"),
            deadline=data.get("deadline"),
            contact=contact,
        )
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("organize_job parse error: %s", exc)
        return OrganizedJob(
            title="Untitled Position",
            company=None,
            description=raw_text[:300],
            location=None,
            payment=None,
            deadline=None,
            contact=contact_info,
        )
    except Exception as exc:
        logger.error("organize_job AI error: %s", exc)
        return OrganizedJob(
            title="Untitled Position",
            company=None,
            description=None,
            location=None,
            payment=None,
            deadline=None,
            contact=contact_info,
        )


async def batch_organize_jobs(
    filtered_jobs: list[dict],
) -> list[tuple[dict, OrganizedJob]]:
    """
    Process a list of valid filtered job dicts concurrently (up to 5 at a time).
    Returns list of (filtered_job, organized_job) pairs.
    """
    import asyncio

    semaphore = asyncio.Semaphore(5)

    async def _process(job: dict) -> tuple[dict, OrganizedJob]:
        async with semaphore:
            result = await organize_job(job["raw_text"], job.get("contact_info"))
            return job, result

    tasks = [_process(j) for j in filtered_jobs]
    return await asyncio.gather(*tasks)

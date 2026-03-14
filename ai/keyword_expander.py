"""
ai/keyword_expander.py — AI-powered job title expansion.

Converts a single user keyword (e.g. "Software Engineer") into a list of
related job titles that improve Telegram channel search recall.
"""

import logging
import re

from ai.openrouter_client import ask_openrouter as ask_poe

logger = logging.getLogger(__name__)

_EXPANSION_PROMPT = """\
Expand the following job title into up to 10 related job titles commonly used in job postings.

Rules:
- Include common abbreviations and alternate role names.
- Include both senior and junior variations where applicable.
- Return ONLY a plain list, one title per line.
- No numbering, no bullets, no extra commentary.

Input: {keyword}
"""


async def expand_keywords(user_keyword: str) -> list[str]:
    """
    Call the Poe AI to expand a job title into related search terms.

    Returns a deduplicated list that always includes the original keyword.
    """
    prompt = _EXPANSION_PROMPT.format(keyword=user_keyword.strip())

    try:
        raw = await ask_poe(prompt)
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        # Remove any accidental numbering like "1. " or "- "
        cleaned = [re.sub(r"^[\d\.\-\*]+\s*", "", line) for line in lines]
        # Deduplicate while preserving order; ensure original is first
        seen: set[str] = set()
        result: list[str] = []
        for kw in [user_keyword] + cleaned:
            key = kw.lower()
            if key not in seen:
                seen.add(key)
                result.append(kw)
        logger.info("Expanded '%s' → %s", user_keyword, result)
        return result[:10]  # cap at 10
    except Exception as exc:
        logger.error("Keyword expansion failed: %s", exc)
        return [user_keyword]

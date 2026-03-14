"""
ai/gemini_client.py — Async wrapper around the Google Gemini API.
Used as the PRIMARY AI provider; openrouter_client is the fallback.

Model: gemini-1.5-flash  (fast, generous free quota)
"""

import asyncio
import logging

import aiohttp

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent?key={api_key}"
)


async def ask_gemini(
    prompt: str,
    *,
    max_tokens: int = 800,
    retries: int = 2,
) -> str:
    """
    Send a prompt to Gemini 1.5 Flash and return the response text.

    Parameters
    ----------
    prompt     : The user prompt string.
    max_tokens : Maximum output tokens.
    retries    : Number of retries on transient failure.

    Returns
    -------
    Response text string.

    Raises
    ------
    RuntimeError if all attempts fail.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    url = _GEMINI_URL.format(api_key=GEMINI_API_KEY)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.3,
        },
    }

    async with aiohttp.ClientSession() as session:
        for attempt in range(retries + 1):
            try:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = (
                            data.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "")
                            .strip()
                        )
                        if text:
                            logger.debug("Gemini responded OK.")
                            return text
                        logger.warning("Gemini returned an empty response.")
                    elif resp.status == 429:
                        logger.warning("Gemini rate limit hit — will fall back to OpenRouter.")
                        raise RuntimeError("Gemini rate limit (429).")
                    elif resp.status in (400, 403):
                        body = await resp.text()
                        logger.error("Gemini error %d: %s", resp.status, body[:300])
                        raise RuntimeError(f"Gemini fatal error {resp.status}: {body[:200]}")
                    else:
                        body = await resp.text()
                        logger.warning("Gemini HTTP %d: %s", resp.status, body[:200])
            except RuntimeError:
                raise  # propagate fatal / rate-limit errors immediately
            except asyncio.TimeoutError:
                logger.warning("Gemini timeout (attempt %d/%d).", attempt + 1, retries + 1)
            except Exception as exc:
                logger.error("Gemini request error: %s", exc)

            if attempt < retries:
                await asyncio.sleep(2)

    raise RuntimeError("Gemini failed after all retries.")

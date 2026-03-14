"""
ai/openrouter_client.py — Unified AI client with Gemini as primary and OpenRouter as fallback.

Priority:
  1. Google Gemini 1.5 Flash  (primary — fast, high free quota)
  2. OpenRouter free model chain (backup):
       meta-llama/llama-3.3-70b-instruct:free
       mistralai/mistral-7b-instruct:free
       google/gemma-3-27b-it:free
       qwen/qwen-2-7b-instruct:free
"""

import asyncio
import logging

import aiohttp

from config import OPENROUTER_API_KEY, OPENROUTER_MODELS

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def _ask_openrouter_only(
    prompt: str,
    *,
    models: list[str] | None = None,
    max_tokens: int = 800,
    retries: int = 2,
) -> str:
    """Internal: try OpenRouter free models in sequence."""
    model_list = models or OPENROUTER_MODELS

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://job-bot",
        "X-Title": "JobBot",
    }

    async with aiohttp.ClientSession() as session:
        for model in model_list:
            for attempt in range(retries + 1):
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                }
                try:
                    async with session.post(
                        OPENROUTER_URL,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            text = data["choices"][0]["message"]["content"].strip()
                            if text:
                                logger.debug("OpenRouter '%s' responded OK.", model)
                                return text
                            logger.warning("OpenRouter '%s' returned empty text.", model)
                        elif resp.status == 429:
                            logger.warning(
                                "OpenRouter rate limit on '%s' — moving to next model.", model
                            )
                            break
                        else:
                            body = await resp.text()
                            logger.error(
                                "OpenRouter HTTP %d for '%s': %s",
                                resp.status,
                                model,
                                body[:200],
                            )
                except asyncio.TimeoutError:
                    logger.warning(
                        "OpenRouter timeout for '%s' (attempt %d).", model, attempt + 1
                    )
                except Exception as exc:
                    logger.error("OpenRouter request error for '%s': %s", model, exc)

                if attempt < retries:
                    logger.warning("Retrying model '%s' (%d/%d)...", model, attempt + 1, retries)
                    await asyncio.sleep(2)

            logger.warning("Model '%s' exhausted — trying next fallback.", model)
            await asyncio.sleep(0.5)

    raise RuntimeError("All OpenRouter models failed for this request.")


async def ask_openrouter(
    prompt: str,
    *,
    models: list[str] | None = None,
    max_tokens: int = 800,
    retries: int = 2,
) -> str:
    """
    Send a prompt to the AI backend.

    Tries Gemini 1.5 Flash first (primary). On any failure, falls back
    to the OpenRouter free model chain automatically.

    Parameters
    ----------
    prompt     : The user prompt string.
    models     : Override OpenRouter model list (only used if Gemini fails).
    max_tokens : Maximum tokens in the response.
    retries    : Per-model retries on failure.

    Returns
    -------
    Response text from the first backend that succeeds.

    Raises
    ------
    RuntimeError if both Gemini and all OpenRouter models fail.
    """
    gemini_exc: Exception | None = None

    # 1. Try Gemini first (primary)
    try:
        from ai.gemini_client import ask_gemini
        result = await ask_gemini(prompt, max_tokens=max_tokens)
        return result
    except Exception as exc:
        gemini_exc = exc
        logger.warning("Gemini unavailable (%s) — falling back to OpenRouter.", exc)

    # 2. Fall back to OpenRouter
    try:
        return await _ask_openrouter_only(
            prompt, models=models, max_tokens=max_tokens, retries=retries
        )
    except RuntimeError as exc:
        raise RuntimeError(
            f"All AI backends failed. Gemini: {gemini_exc} | OpenRouter: {exc}"
        ) from exc

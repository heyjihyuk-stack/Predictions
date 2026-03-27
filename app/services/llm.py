from __future__ import annotations

"""OpenAI-compatible LLM client wrapper."""

import json
import logging

from openai import OpenAI

from config.settings import get_settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = OpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)
    return _client


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.7, **kwargs) -> str:
    """Send a chat completion request and return the response text."""
    settings = get_settings()
    client = _get_client()
    response = client.chat.completions.create(
        model=model or settings.LLM_MODEL,
        messages=messages,
        temperature=temperature,
        **kwargs,
    )
    return response.choices[0].message.content


def chat_json(messages: list[dict], model: str | None = None, **kwargs) -> dict:
    """Send a chat completion and parse the response as JSON."""
    raw = chat(messages, model=model, **kwargs)
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON, returning raw text")
        return {"raw": raw}

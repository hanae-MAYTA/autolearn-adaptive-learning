"""Minimal client for the Groq chat-completions API (OpenAI-compatible)."""
from __future__ import annotations

import requests

from config import GROQ_API_KEY, GROQ_MODEL

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def groq_available() -> bool:
    return bool(GROQ_API_KEY)


def groq_chat(messages: list[dict], timeout: int = 40, **params) -> str:
    """Send a chat request and return the text of the first choice.

    Raises ``RuntimeError`` when no API key is configured and ``requests.HTTPError``
    on API errors, so callers can fall back to local logic.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set")
    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={"model": GROQ_MODEL, "messages": messages, **params},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

"""Shared Anthropic Claude client used by all stages that call the LLM."""

import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-20250514"

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    """Return a shared Anthropic client, initialising it on first call."""
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def simple_completion(system: str, user: str, max_tokens: int = 4096) -> str:
    """Send a single system+user message and return the text content."""
    client = get_client()
    message = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text

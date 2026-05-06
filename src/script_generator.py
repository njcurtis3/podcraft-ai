"""Stage 2 — transform a research brief into a two-host podcast script.

# THEORY: Agenda-setting theory (McCombs & Shaw, 1972) — the script generator frames
# which aspects of the brief get foregrounded, shaping what the audience focuses on.
# THEORY: Parasocial interaction (Horton & Wohl, 1956) — HOST_A/HOST_B personas are
# designed to create a sense of intimacy and familiarity with the listener.
"""

import json
import os
from typing import Any

from dotenv import load_dotenv

from src.utils.llm import simple_completion
from src.utils.logger import logger
from src.utils.validators import validate_script

load_dotenv()

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "script_prompt.txt")


class ScriptError(Exception):
    """Raised when script generation fails or produces invalid output."""


def _load_system_prompt() -> str:
    """Load the script system prompt from disk."""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _strip_fences(text: str) -> str:
    """Strip accidental markdown code fences from LLM output."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def generate_script(brief: dict[str, Any]) -> dict[str, Any]:
    """Generate a two-host podcast script from a research brief.

    Args:
        brief: Validated research brief dict from Stage 1.

    Returns:
        A dict conforming to the script schema.

    Raises:
        ScriptError: If the LLM returns unparseable or invalid JSON.
    """
    logger.info("Stage 2 — generating script for topic: %s", brief.get("topic", "unknown"))
    system_prompt = _load_system_prompt()
    user_message = (
        "Here is the research brief for this episode. "
        "Write the full two-host podcast script as instructed.\n\n"
        + json.dumps(brief, indent=2)
    )

    raw = simple_completion(system=system_prompt, user=user_message, max_tokens=8192)
    cleaned = _strip_fences(raw)

    try:
        script = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ScriptError(f"Could not parse script JSON from LLM response: {exc}\n\nRaw output:\n{raw[:500]}") from exc

    try:
        validate_script(script)
    except Exception as exc:
        raise ScriptError(f"Script failed schema validation: {exc}") from exc

    total_words = sum(
        len(turn["text"].split())
        for seg in script["segments"]
        for turn in seg["turns"]
    )
    logger.info(
        "Stage 2 — script complete. %d segments, ~%d words.",
        len(script["segments"]),
        total_words,
    )
    return script

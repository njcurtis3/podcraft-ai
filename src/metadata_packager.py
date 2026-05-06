"""Stage 4 — generate RSS-compatible metadata and write the episode sidecar JSON."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from src.utils.llm import simple_completion
from src.utils.logger import logger

load_dotenv()

DESCRIPTION_SYSTEM = (
    "You are a podcast producer writing episode show notes. "
    "Given an episode title and a list of key topics, write a 2–3 sentence episode description "
    "suitable for an RSS feed. Be concise, engaging, and avoid spoilers. "
    "Return only the description text — no labels, no quotes."
)

TAGS_SYSTEM = (
    "You are a podcast metadata specialist. "
    "Given an episode title and brief, generate 5–8 short topic tags (single words or two-word phrases). "
    "Return them as a JSON array of strings only — no other text."
)


class MetadataError(Exception):
    """Raised when metadata generation fails."""


def _ms_to_hhmmss(milliseconds: int) -> str:
    """Convert pydub millisecond duration to HH:MM:SS for RSS feeds."""
    seconds = milliseconds // 1000
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _generate_description(script: dict[str, Any]) -> str:
    """Use a brief Claude call to generate a 2–3 sentence episode description."""
    title = script.get("title", "Untitled")
    angles = [
        seg["segment"]
        for seg in script.get("segments", [])
    ]
    user_msg = f"Episode title: {title}\nSegments covered: {', '.join(angles)}"
    return simple_completion(system=DESCRIPTION_SYSTEM, user=user_msg, max_tokens=256).strip()


def _generate_tags(script: dict[str, Any]) -> list[str]:
    """Use a brief Claude call to generate 5–8 topic tags."""
    title = script.get("title", "Untitled")
    # Pull a few representative lines from the script for context
    sample_lines: list[str] = []
    for seg in script.get("segments", []):
        for turn in seg.get("turns", [])[:2]:
            sample_lines.append(turn.get("text", "")[:100])
        if len(sample_lines) >= 6:
            break

    user_msg = f"Episode title: {title}\nSample dialogue: {' | '.join(sample_lines)}"
    raw = simple_completion(system=TAGS_SYSTEM, user=user_msg, max_tokens=128).strip()
    raw = raw.strip("```json").strip("```").strip()
    try:
        tags = json.loads(raw)
        if isinstance(tags, list):
            return [str(t) for t in tags[:8]]
    except json.JSONDecodeError:
        pass
    # Fallback: split by comma
    return [t.strip().strip('"') for t in raw.split(",") if t.strip()][:8]


def _buzzsprout_upload(meta: dict[str, Any]) -> None:
    """Attempt to upload the episode to Buzzsprout if credentials are set."""
    api_key = os.getenv("BUZZSPROUT_API_KEY")
    podcast_id = os.getenv("BUZZSPROUT_PODCAST_ID")
    if not api_key or not podcast_id:
        return

    mp3_path = meta.get("mp3_path", "")
    if not Path(mp3_path).exists():
        logger.warning("Buzzsprout upload skipped — mp3 not found at %s.", mp3_path)
        return

    url = f"https://www.buzzsprout.com/api/{podcast_id}/episodes.json"
    headers = {"Authorization": f"Token token={api_key}"}
    try:
        with open(mp3_path, "rb") as f:
            response = requests.post(
                url,
                headers=headers,
                data={
                    "title": meta["title"],
                    "description": meta["description"],
                    "tags": ", ".join(meta.get("tags", [])),
                },
                files={"audio_file": f},
                timeout=120,
            )
        if response.status_code in (200, 201):
            logger.info("Buzzsprout upload successful. Episode ID: %s", response.json().get("id"))
        else:
            logger.warning("Buzzsprout upload failed with status %d: %s", response.status_code, response.text[:200])
    except requests.RequestException as exc:
        logger.warning("Buzzsprout upload error (non-fatal): %s", exc)


def package_metadata(
    script: dict[str, Any],
    episode_num: int,
    mp3_path: str,
    mp3_duration_ms: int = 0,
) -> str:
    """Generate and write the episode sidecar metadata JSON.

    Args:
        script: Validated script dict from Stage 2.
        episode_num: Episode number for file naming.
        mp3_path: Path to the assembled mp3.
        mp3_duration_ms: Duration of the mp3 in milliseconds (0 if unknown).

    Returns:
        Path to the written sidecar JSON file.

    Raises:
        MetadataError: On generation or write failure.
    """
    logger.info("Stage 4 — generating metadata for episode %d.", episode_num)

    description = _generate_description(script)
    tags = _generate_tags(script)

    chapters = [seg["segment"] for seg in script.get("segments", [])]
    duration_str = _ms_to_hhmmss(mp3_duration_ms) if mp3_duration_ms else script.get("duration_estimate", "")

    meta: dict[str, Any] = {
        "title": script.get("title", f"Episode {episode_num}"),
        "episode": episode_num,
        "published": datetime.now(timezone.utc).isoformat(),
        "duration_estimate": duration_str,
        "description": description,
        "tags": tags,
        "chapters": chapters,
        "mp3_path": mp3_path,
    }

    episodes_dir = Path(__file__).parent.parent / "episodes"
    episodes_dir.mkdir(exist_ok=True)
    out_path = str(episodes_dir / f"episode_{episode_num}_meta.json")

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        raise MetadataError(f"Failed to write metadata file: {exc}") from exc

    logger.info("Stage 4 — metadata written to %s.", out_path)
    _buzzsprout_upload(meta)
    return out_path

"""Stage 3 — synthesize TTS audio for each turn and assemble the final episode.

# THEORY: Production workflow theory (McLeish & Link, 2016) — each turn is an atomic
# production unit, assembled in sequence like a traditional broadcast edit.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from pydub import AudioSegment

from src.utils.logger import logger

load_dotenv()

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
TTS_MODEL = "eleven_turbo_v2"
MAX_TTS_CHARS = 5000
TURN_SILENCE_MS = 300
SEGMENT_SILENCE_MS = 800
MUSIC_VOLUME_DB = -18
EXPORT_BITRATE = "192k"
TMP_DIR = Path(tempfile.gettempdir()) / "podcraft"


class AudioError(Exception):
    """Raised when audio synthesis or assembly fails."""


def _check_ffmpeg() -> None:
    """Raise EnvironmentError if ffmpeg is not on PATH."""
    if not shutil.which("ffmpeg"):
        raise EnvironmentError(
            "ffmpeg is not found on PATH. Install ffmpeg and ensure it is accessible."
        )


def _get_voice_ids() -> tuple[str, str]:
    """Return (HOST_A voice ID, HOST_B voice ID) from env."""
    voice_a = os.getenv("ELEVENLABS_VOICE_ID_HOST_A")
    voice_b = os.getenv("ELEVENLABS_VOICE_ID_HOST_B")
    if not voice_a or not voice_b:
        raise EnvironmentError("ELEVENLABS_VOICE_ID_HOST_A and ELEVENLABS_VOICE_ID_HOST_B must be set.")
    return voice_a, voice_b


def _synthesize_turn(text: str, voice_id: str, api_key: str) -> bytes:
    """Call ElevenLabs TTS and return raw mp3 bytes for a single turn."""
    if len(text) > MAX_TTS_CHARS:
        text = text[:MAX_TTS_CHARS]
        logger.warning("Turn text truncated to %d characters for ElevenLabs limit.", MAX_TTS_CHARS)

    url = ELEVENLABS_API_URL.format(voice_id=voice_id)
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": TTS_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise AudioError(
            f"ElevenLabs API error {response.status_code}: {response.text[:200]}"
        )
    return response.content


def _audio_from_bytes(mp3_bytes: bytes) -> AudioSegment:
    """Write mp3 bytes to a temp file, load with pydub, then delete."""
    tmp_path = TMP_DIR / f"turn_{os.getpid()}_{id(mp3_bytes)}.mp3"
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.write_bytes(mp3_bytes)
        if tmp_path.stat().st_size == 0:
            raise AudioError("ElevenLabs returned a zero-byte audio file.")
        return AudioSegment.from_mp3(str(tmp_path))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _load_background_music(episode_length_ms: int) -> AudioSegment | None:
    """Load a background track from music/, loop to fill episode, return at -18dB."""
    music_dir = Path(__file__).parent.parent / "music"
    tracks = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
    if not tracks:
        logger.warning("No background music files found in music/ — skipping.")
        return None

    track = AudioSegment.from_file(str(tracks[0]))
    # Loop until longer than the episode
    while len(track) < episode_length_ms:
        track = track + track
    track = track[:episode_length_ms]
    return track + MUSIC_VOLUME_DB  # reduce to -18dB under dialogue


def assemble_episode(
    script: dict[str, Any],
    episode_num: int,
    dev_mode: bool = False,
) -> str:
    """Synthesize and assemble an episode mp3 from a script.

    Args:
        script: Validated script dict from Stage 2.
        episode_num: Used to name the output file.
        dev_mode: If True, only synthesize the first 2 turns (cost control).

    Returns:
        Path to the written episode mp3.

    Raises:
        AudioError: On synthesis or assembly failure.
        EnvironmentError: If ffmpeg or API keys are missing.
    """
    _check_ffmpeg()

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise EnvironmentError("ELEVENLABS_API_KEY is not set.")

    voice_a, voice_b = _get_voice_ids()
    voice_map = {"HOST_A": voice_a, "HOST_B": voice_b}

    # Flatten all turns across all segments, tagging segment boundaries
    all_turns: list[tuple[str, str, bool]] = []  # (speaker, text, is_segment_start)
    for seg_idx, segment in enumerate(script["segments"]):
        for turn_idx, turn in enumerate(segment["turns"]):
            is_start = turn_idx == 0 and seg_idx > 0
            all_turns.append((turn["speaker"], turn["text"], is_start))

    if dev_mode:
        logger.info("dev_mode=True — limiting TTS to first 2 turns.")
        all_turns = all_turns[:2]

    logger.info("Stage 3 — synthesizing %d turns via ElevenLabs.", len(all_turns))

    clips: list[AudioSegment] = []
    for idx, (speaker, text, is_segment_start) in enumerate(all_turns):
        logger.info("  Synthesizing turn %d/%d (%s, %d chars)…", idx + 1, len(all_turns), speaker, len(text))
        mp3_bytes = _synthesize_turn(text, voice_map[speaker], api_key)
        clip = _audio_from_bytes(mp3_bytes)
        clips.append(clip)

    # Assemble with silences
    combined = AudioSegment.empty()
    seg_boundary_indices: set[int] = {
        i for i, (_, _, is_start) in enumerate(all_turns) if is_start
    }
    for i, clip in enumerate(clips):
        if i > 0:
            silence_ms = SEGMENT_SILENCE_MS if i in seg_boundary_indices else TURN_SILENCE_MS
            combined += AudioSegment.silent(duration=silence_ms)
        combined += clip

    # Overlay background music
    music = _load_background_music(len(combined))
    if music is not None:
        combined = combined.overlay(music)

    # Normalize and export
    final = combined.normalize()
    episodes_dir = Path(__file__).parent.parent / "episodes"
    episodes_dir.mkdir(exist_ok=True)
    out_path = str(episodes_dir / f"episode_{episode_num}.mp3")
    final.export(out_path, format="mp3", bitrate=EXPORT_BITRATE)

    logger.info("Stage 3 — episode written to %s (%.1f sec).", out_path, len(final) / 1000)
    return out_path

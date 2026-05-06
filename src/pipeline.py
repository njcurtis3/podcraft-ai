"""Entry point — orchestrates all four pipeline stages end-to-end."""

import argparse
import json
import time
import traceback
from pathlib import Path
from typing import Any

from src.audio_assembler import assemble_episode
from src.metadata_packager import package_metadata
from src.research_agent import run_research
from src.script_generator import generate_script
from src.utils.logger import logger


def run_pipeline(topic: str, episode_num: int, dev_mode: bool = False) -> dict[str, Any]:
    """Run all four pipeline stages in sequence.

    Args:
        topic: The subject to research and produce an episode about.
        episode_num: Episode number used for output file naming.
        dev_mode: If True, limits TTS to first 2 turns to conserve API credits.

    Returns:
        dict with keys: brief, script, mp3_path, meta_path
    """
    episodes_dir = Path(__file__).parent.parent / "episodes"
    episodes_dir.mkdir(exist_ok=True)

    results: dict[str, Any] = {}

    # ── Stage 1: Research ────────────────────────────────────────────────────
    logger.info("━━━ Stage 1: Research ━━━")
    t0 = time.perf_counter()
    try:
        brief = run_research(topic)
    except Exception:
        logger.error("Stage 1 failed:\n%s", traceback.format_exc())
        raise
    elapsed = time.perf_counter() - t0
    logger.info("Stage 1 complete in %.1fs.", elapsed)

    brief_path = episodes_dir / f"episode_{episode_num}_brief.json"
    brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Brief saved to %s.", brief_path)
    results["brief"] = brief

    # ── Stage 2: Script ──────────────────────────────────────────────────────
    logger.info("━━━ Stage 2: Script ━━━")
    t0 = time.perf_counter()
    try:
        script = generate_script(brief)
    except Exception:
        logger.error("Stage 2 failed:\n%s", traceback.format_exc())
        raise
    elapsed = time.perf_counter() - t0
    logger.info("Stage 2 complete in %.1fs.", elapsed)

    script_path = episodes_dir / f"episode_{episode_num}_script.json"
    script_path.write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Script saved to %s.", script_path)
    results["script"] = script

    # ── Stage 3: Audio ───────────────────────────────────────────────────────
    logger.info("━━━ Stage 3: Audio Assembly ━━━")
    t0 = time.perf_counter()
    try:
        mp3_path = assemble_episode(script, episode_num, dev_mode=dev_mode)
    except Exception:
        logger.error("Stage 3 failed:\n%s", traceback.format_exc())
        raise
    elapsed = time.perf_counter() - t0
    logger.info("Stage 3 complete in %.1fs.", elapsed)
    results["mp3_path"] = mp3_path

    # Get duration for metadata
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(mp3_path)
        mp3_duration_ms = len(audio)
    except Exception:
        mp3_duration_ms = 0

    # ── Stage 4: Metadata ────────────────────────────────────────────────────
    logger.info("━━━ Stage 4: Metadata ━━━")
    t0 = time.perf_counter()
    try:
        meta_path = package_metadata(script, episode_num, mp3_path, mp3_duration_ms)
    except Exception:
        logger.error("Stage 4 failed:\n%s", traceback.format_exc())
        raise
    elapsed = time.perf_counter() - t0
    logger.info("Stage 4 complete in %.1fs.", elapsed)
    results["meta_path"] = meta_path

    logger.info("Pipeline complete. Episode %d ready.", episode_num)
    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PodCraft AI — generate a podcast episode end-to-end.")
    parser.add_argument("--topic", required=True, help="Topic for the episode.")
    parser.add_argument("--episode", type=int, required=True, help="Episode number.")
    parser.add_argument("--dev", action="store_true", help="Run in dev mode (2 TTS turns only).")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_pipeline(topic=args.topic, episode_num=args.episode, dev_mode=args.dev)

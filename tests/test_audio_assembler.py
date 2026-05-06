"""Tests for Stage 3 — audio_assembler.py.

All tests use sample_script.json and mock ElevenLabs to avoid API calls.
Run with dev_mode=True to limit synthesis to 2 turns.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audio_assembler import AudioError, _ms_to_hhmmss  # noqa: F401 — imported for completeness

FIXTURES = Path(__file__).parent / "fixtures"


def load_script() -> dict:
    return json.loads((FIXTURES / "sample_script.json").read_text(encoding="utf-8"))


class TestCheckFfmpeg:
    def test_raises_if_ffmpeg_missing(self):
        from src.audio_assembler import _check_ffmpeg
        with patch("shutil.which", return_value=None):
            with pytest.raises(EnvironmentError, match="ffmpeg"):
                _check_ffmpeg()

    def test_passes_if_ffmpeg_present(self):
        from src.audio_assembler import _check_ffmpeg
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            _check_ffmpeg()  # should not raise


class TestGetVoiceIds:
    def test_raises_if_env_missing(self, monkeypatch):
        from src.audio_assembler import _get_voice_ids
        monkeypatch.delenv("ELEVENLABS_VOICE_ID_HOST_A", raising=False)
        monkeypatch.delenv("ELEVENLABS_VOICE_ID_HOST_B", raising=False)
        with pytest.raises(EnvironmentError):
            _get_voice_ids()

    def test_returns_ids_from_env(self, monkeypatch):
        from src.audio_assembler import _get_voice_ids
        monkeypatch.setenv("ELEVENLABS_VOICE_ID_HOST_A", "voice-aaa")
        monkeypatch.setenv("ELEVENLABS_VOICE_ID_HOST_B", "voice-bbb")
        a, b = _get_voice_ids()
        assert a == "voice-aaa"
        assert b == "voice-bbb"


class TestAssembleEpisode:
    def _fake_mp3_bytes(self) -> bytes:
        # Minimal valid mp3 header bytes (just enough for pydub with ffmpeg)
        return b"\xff\xfb\x90\x00" + b"\x00" * 100

    @patch("src.audio_assembler._check_ffmpeg")
    @patch("src.audio_assembler._synthesize_turn")
    @patch("src.audio_assembler._audio_from_bytes")
    @patch("src.audio_assembler._load_background_music", return_value=None)
    def test_dev_mode_limits_to_two_turns(
        self, _music, mock_audio, mock_synth, _ffmpeg, monkeypatch, tmp_path
    ):
        from pydub import AudioSegment
        from src.audio_assembler import assemble_episode

        monkeypatch.setenv("ELEVENLABS_API_KEY", "fake")
        monkeypatch.setenv("ELEVENLABS_VOICE_ID_HOST_A", "va")
        monkeypatch.setenv("ELEVENLABS_VOICE_ID_HOST_B", "vb")

        mock_synth.return_value = b"\x00" * 10
        mock_audio.return_value = AudioSegment.silent(duration=500)

        script = load_script()
        with patch("src.audio_assembler.Path") as mock_path_cls:
            # Route output to tmp_path
            real_path = Path
            def path_side(*args):
                p = real_path(*args)
                if "episodes" in str(p):
                    return tmp_path
                return p
            mock_path_cls.side_effect = path_side

            # Just verify synthesis call count
            assemble_episode(script, episode_num=99, dev_mode=True)

        assert mock_synth.call_count == 2

    @patch("src.audio_assembler._check_ffmpeg")
    def test_raises_if_elevenlabs_key_missing(self, _ffmpeg, monkeypatch):
        from src.audio_assembler import assemble_episode
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        with pytest.raises(EnvironmentError, match="ELEVENLABS_API_KEY"):
            assemble_episode(load_script(), episode_num=1)

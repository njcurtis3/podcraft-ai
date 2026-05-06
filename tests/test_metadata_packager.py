"""Tests for Stage 4 — metadata_packager.py."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.metadata_packager import _ms_to_hhmmss, _generate_tags, package_metadata

FIXTURES = Path(__file__).parent / "fixtures"


def load_script() -> dict:
    return json.loads((FIXTURES / "sample_script.json").read_text(encoding="utf-8"))


class TestMsToHhmmss:
    def test_zero(self):
        assert _ms_to_hhmmss(0) == "00:00:00"

    def test_one_hour(self):
        assert _ms_to_hhmmss(3_600_000) == "01:00:00"

    def test_mixed(self):
        ms = (1 * 3600 + 23 * 60 + 45) * 1000
        assert _ms_to_hhmmss(ms) == "01:23:45"

    def test_sub_minute(self):
        assert _ms_to_hhmmss(45_000) == "00:00:45"


class TestGenerateTags:
    def test_returns_list_from_json(self):
        script = load_script()
        with patch("src.metadata_packager.simple_completion", return_value='["ai", "journalism", "media"]'):
            tags = _generate_tags(script)
        assert tags == ["ai", "journalism", "media"]

    def test_fallback_on_bad_json(self):
        script = load_script()
        with patch("src.metadata_packager.simple_completion", return_value="ai, journalism, media"):
            tags = _generate_tags(script)
        assert isinstance(tags, list)
        assert "ai" in tags

    def test_caps_at_eight_tags(self):
        script = load_script()
        many = '["a","b","c","d","e","f","g","h","i","j"]'
        with patch("src.metadata_packager.simple_completion", return_value=many):
            tags = _generate_tags(script)
        assert len(tags) <= 8


class TestPackageMetadata:
    def test_writes_sidecar_json(self, tmp_path):
        script = load_script()
        fake_mp3 = tmp_path / "episode_1.mp3"
        fake_mp3.write_bytes(b"fake")

        import src.metadata_packager as mp_mod
        original_path_class = mp_mod.Path

        # Redirect episodes dir to tmp_path
        class PatchedPath(type(original_path_class())):
            def __new__(cls, *args, **kwargs):
                return original_path_class(*args, **kwargs)

        with patch("src.metadata_packager.simple_completion", return_value="A great AI journalism episode."), \
             patch("src.metadata_packager._generate_tags", return_value=["ai", "journalism"]), \
             patch("src.metadata_packager._buzzsprout_upload"), \
             patch.object(mp_mod, "Path", wraps=original_path_class) as mock_path:

            # Make episodes dir point at tmp_path
            real_file = original_path_class(__file__)
            mock_path.return_value = original_path_class(tmp_path)

            # Call directly — output lands in the real episodes/ dir
            # Use tmp_path as the output dir by patching the resolved path
            pass

        # Straightforward test: actually write to the real episodes/ dir and verify
        with patch("src.metadata_packager.simple_completion", return_value="A great AI journalism episode."), \
             patch("src.metadata_packager._generate_tags", return_value=["ai", "journalism"]), \
             patch("src.metadata_packager._buzzsprout_upload"):
            meta_path = package_metadata(
                script=script,
                episode_num=999,
                mp3_path=str(fake_mp3),
                mp3_duration_ms=1_260_000,
            )

        assert Path(meta_path).exists()
        meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        assert meta["episode"] == 999
        assert meta["title"] == script["title"]
        assert "published" in meta
        assert meta["duration_estimate"] == "00:21:00"
        assert meta["tags"] == ["ai", "journalism"]

        # Clean up
        Path(meta_path).unlink(missing_ok=True)

    def test_chapters_match_segments(self):
        script = load_script()
        fake_mp3 = Path(__file__).parent / "fixtures" / "nonexistent.mp3"

        with patch("src.metadata_packager.simple_completion", return_value="Desc."), \
             patch("src.metadata_packager._generate_tags", return_value=["tag"]), \
             patch("src.metadata_packager._buzzsprout_upload"):
            meta_path = package_metadata(
                script=script,
                episode_num=998,
                mp3_path=str(fake_mp3),
            )

        meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        assert meta["chapters"] == ["intro", "main", "wrap"]
        Path(meta_path).unlink(missing_ok=True)

"""Tests for Stage 2 — script_generator.py."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.script_generator import ScriptError, _strip_fences, generate_script
from src.utils.validators import validate_script

FIXTURES = Path(__file__).parent / "fixtures"


def load_brief() -> dict:
    return json.loads((FIXTURES / "sample_brief.json").read_text(encoding="utf-8"))


def load_script() -> dict:
    return json.loads((FIXTURES / "sample_script.json").read_text(encoding="utf-8"))


class TestStripFences:
    def test_strips_json_fence(self):
        raw = "```json\n{}\n```"
        assert _strip_fences(raw) == "{}"

    def test_strips_plain_fence(self):
        raw = "```\n{}\n```"
        assert _strip_fences(raw) == "{}"

    def test_no_fence_passthrough(self):
        raw = '{"key": "value"}'
        assert _strip_fences(raw) == raw


class TestValidateScript:
    def test_sample_script_validates(self):
        validate_script(load_script())  # should not raise

    def test_invalid_segment_type_fails(self):
        import jsonschema
        script = load_script()
        script["segments"][0]["segment"] = "monologue"
        with pytest.raises(jsonschema.ValidationError):
            validate_script(script)

    def test_invalid_speaker_fails(self):
        import jsonschema
        script = load_script()
        script["segments"][0]["turns"][0]["speaker"] = "HOST_C"
        with pytest.raises(jsonschema.ValidationError):
            validate_script(script)


class TestGenerateScript:
    def test_generate_script_from_fixture_brief(self):
        sample_script = load_script()
        with patch("src.script_generator.simple_completion", return_value=json.dumps(sample_script)):
            with patch("src.script_generator._load_system_prompt", return_value="system"):
                result = generate_script(load_brief())
        assert result["title"] == sample_script["title"]
        assert len(result["segments"]) == 3

    def test_generate_script_raises_on_bad_json(self):
        with patch("src.script_generator.simple_completion", return_value="not json"):
            with patch("src.script_generator._load_system_prompt", return_value="system"):
                with pytest.raises(ScriptError):
                    generate_script(load_brief())

    def test_generate_script_strips_fences(self):
        sample_script = load_script()
        fenced = "```json\n" + json.dumps(sample_script) + "\n```"
        with patch("src.script_generator.simple_completion", return_value=fenced):
            with patch("src.script_generator._load_system_prompt", return_value="system"):
                result = generate_script(load_brief())
        assert result["title"] == sample_script["title"]

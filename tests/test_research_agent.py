"""Tests for Stage 1 — research_agent.py."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.research_agent import ResearchError, _extract_json, run_research
from src.utils.validators import validate_brief


VALID_BRIEF = {
    "topic": "AI in journalism",
    "key_angles": ["automation", "job displacement"],
    "facts_and_stats": ["AP has used AI since 2014"],
    "expert_perspectives": ["Charlie Beckett: AI changes journalism"],
    "controversy_or_nuance": "Some see opportunity, others see risk.",
    "sources": ["https://example.com/source1"],
}


class TestExtractJson:
    def test_clean_json(self):
        raw = json.dumps(VALID_BRIEF)
        result = _extract_json(raw)
        assert result["topic"] == "AI in journalism"

    def test_strips_markdown_fences(self):
        raw = "```json\n" + json.dumps(VALID_BRIEF) + "\n```"
        result = _extract_json(raw)
        assert result["topic"] == "AI in journalism"

    def test_json_embedded_in_text(self):
        raw = "Here is the brief:\n" + json.dumps(VALID_BRIEF) + "\nDone."
        result = _extract_json(raw)
        assert result["topic"] == "AI in journalism"

    def test_raises_on_garbage(self):
        with pytest.raises(ResearchError):
            _extract_json("this is not json at all")


class TestValidateBrief:
    def test_valid_brief_passes(self):
        validate_brief(VALID_BRIEF)  # should not raise

    def test_missing_required_field_fails(self):
        import jsonschema
        bad = {k: v for k, v in VALID_BRIEF.items() if k != "sources"}
        with pytest.raises(jsonschema.ValidationError):
            validate_brief(bad)

    def test_empty_key_angles_fails(self):
        import jsonschema
        bad = {**VALID_BRIEF, "key_angles": []}
        with pytest.raises(jsonschema.ValidationError):
            validate_brief(bad)


class TestRunResearch:
    @patch("src.research_agent._build_agent")
    def test_run_research_returns_valid_brief(self, mock_build):
        mock_executor = MagicMock()
        mock_executor.invoke.return_value = {"output": json.dumps(VALID_BRIEF)}
        mock_build.return_value = mock_executor

        with patch("src.research_agent._load_system_prompt", return_value="system"):
            result = run_research("AI in journalism")

        assert result["topic"] == "AI in journalism"
        assert isinstance(result["sources"], list)

    @patch("src.research_agent._build_agent")
    def test_run_research_deduplicates_sources(self, mock_build):
        brief_with_dupes = {
            **VALID_BRIEF,
            "sources": ["https://a.com", "https://a.com", "https://b.com"],
        }
        mock_executor = MagicMock()
        mock_executor.invoke.return_value = {"output": json.dumps(brief_with_dupes)}
        mock_build.return_value = mock_executor

        with patch("src.research_agent._load_system_prompt", return_value="system"):
            result = run_research("AI in journalism")

        assert len(result["sources"]) == 2

    @patch("src.research_agent._build_agent")
    def test_run_research_raises_on_empty_output(self, mock_build):
        mock_executor = MagicMock()
        mock_executor.invoke.return_value = {"output": ""}
        mock_build.return_value = mock_executor

        with patch("src.research_agent._load_system_prompt", return_value="system"):
            with pytest.raises(ResearchError):
                run_research("AI in journalism")

    @patch("src.research_agent._build_agent")
    def test_run_research_raises_on_no_sources(self, mock_build):
        no_sources = {**VALID_BRIEF, "sources": []}
        mock_executor = MagicMock()
        mock_executor.invoke.return_value = {"output": json.dumps(no_sources)}
        mock_build.return_value = mock_executor

        with patch("src.research_agent._load_system_prompt", return_value="system"):
            with pytest.raises(ResearchError):
                run_research("AI in journalism")

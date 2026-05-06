"""Shared pytest configuration and fixtures."""

import os

import pytest


@pytest.fixture(autouse=True)
def _stub_env_keys(monkeypatch):
    """Ensure API key env vars are set to dummy values for all tests.

    This prevents modules from raising EnvironmentError on import when keys
    are not present in the developer's shell.
    """
    defaults = {
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "ELEVENLABS_API_KEY": "test-elevenlabs-key",
        "TAVILY_API_KEY": "test-tavily-key",
        "ELEVENLABS_VOICE_ID_HOST_A": "test-voice-a",
        "ELEVENLABS_VOICE_ID_HOST_B": "test-voice-b",
    }
    for key, value in defaults.items():
        if not os.getenv(key):
            monkeypatch.setenv(key, value)

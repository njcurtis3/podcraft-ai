"""Stage 1 — research a topic and return a validated research brief.

# THEORY: Gatekeeping theory (Shoemaker & Vos, 2009) — the agent acts as a gatekeeper,
# filtering the web's noise into a curated set of angles, facts, and sources.
"""

import json
import os
from typing import Any

from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.prompts import PromptTemplate

from src.utils.logger import logger
from src.utils.validators import validate_brief

load_dotenv()

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "research_prompt.txt")
MODEL = "claude-sonnet-4-20250514"
MAX_SEARCHES = 5


class ResearchError(Exception):
    """Raised when the research agent cannot produce a usable brief."""


def _load_system_prompt() -> str:
    """Load the research system prompt from disk."""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _build_agent() -> AgentExecutor:
    """Construct a LangChain ReAct agent with Tavily search."""
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        raise EnvironmentError("TAVILY_API_KEY is not set.")

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set.")

    llm = ChatAnthropic(model=MODEL, anthropic_api_key=anthropic_key)
    tools = [TavilySearchResults(max_results=MAX_SEARCHES)]

    # ReAct prompt template required by LangChain's create_react_agent
    react_template = (
        "{system_prompt}\n\n"
        "You have access to the following tools:\n{tools}\n\n"
        "Use the following format:\n"
        "Thought: think about what to do\n"
        "Action: the tool to use (one of [{tool_names}])\n"
        "Action Input: the input to the tool\n"
        "Observation: the result of the tool\n"
        "... (repeat Thought/Action/Observation at least 3 times for source diversity)\n"
        "Thought: I now have enough information\n"
        "Final Answer: <valid JSON brief>\n\n"
        "Begin!\n\n"
        "Question: {input}\n"
        "{agent_scratchpad}"
    )
    prompt = PromptTemplate.from_template(react_template)
    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=10)


def _extract_json(raw: str) -> dict[str, Any]:
    """Pull the JSON object out of the agent's Final Answer string."""
    text = raw.strip().strip("```json").strip("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # Try to find a JSON block inside the string
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        raise ResearchError(f"Could not parse research brief JSON: {exc}") from exc


def run_research(topic: str) -> dict[str, Any]:
    """Research a topic and return a validated brief dict.

    Args:
        topic: The podcast topic to research.

    Returns:
        A dict conforming to the research brief schema.

    Raises:
        ResearchError: If the agent returns empty or unparseable results.
        EnvironmentError: If required API keys are missing.
    """
    logger.info("Stage 1 — starting research for topic: %s", topic)
    system_prompt = _load_system_prompt()
    agent_executor = _build_agent()

    result = agent_executor.invoke(
        {
            "system_prompt": system_prompt,
            "input": f"Research the following topic for a podcast episode: {topic}",
        }
    )

    raw_output: str = result.get("output", "")
    if not raw_output:
        raise ResearchError("Research agent returned empty output.")

    brief = _extract_json(raw_output)

    if not brief.get("sources"):
        raise ResearchError("Research agent returned no sources — aborting to avoid empty data downstream.")

    # Deduplicate sources
    brief["sources"] = list(dict.fromkeys(brief["sources"]))

    try:
        validate_brief(brief)
    except Exception as exc:
        raise ResearchError(f"Research brief failed schema validation: {exc}") from exc

    logger.info("Stage 1 — research complete. %d sources, %d angles.", len(brief["sources"]), len(brief["key_angles"]))
    return brief

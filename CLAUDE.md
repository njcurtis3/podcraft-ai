# CLAUDE.md — podcraft-ai

> End-to-end AI pipeline that researches a topic, writes a two-host script, synthesizes voices, and exports a broadcast-ready podcast episode.

This file is the authoritative reference for all development on this project. Read it in full at the start of every session before writing any code.

---

## Project Identity

| Field | Value |
|---|---|
| Repo | `podcraft-ai` |
| Owner | Nathan Curtis |
| Course | MCOM 4900 — Independent Study, WTAMU |
| Supervisor | Randy Ray, Director of Broadcast Engineering |
| Language | Python 3.11+ |
| Entry point | `src/pipeline.py` |

---

## Repository Structure

```
podcraft-ai/
├── CLAUDE.md                  # This file — always read first
├── CONTEXT.md                 # Project overview and stage summaries
├── README.md                  # Public-facing documentation
├── .env.example               # Environment variable template (never commit .env)
├── .gitignore
├── requirements.txt
├── episodes/                  # Output directory — .mp3 and _meta.json files
├── music/                     # Royalty-free background tracks
├── src/
│   ├── pipeline.py            # Main entry point — run_pipeline()
│   ├── research_agent.py      # Stage 1 — topic research via Tavily + LLM
│   ├── script_generator.py    # Stage 2 — two-host script from research brief
│   ├── audio_assembler.py     # Stage 3 — TTS synthesis + pydub assembly
│   ├── metadata_packager.py   # Stage 4 — RSS metadata + sidecar JSON
│   └── utils/
│       ├── llm.py             # Shared Claude API client
│       ├── logger.py          # Structured logging
│       └── validators.py      # JSON schema validators for inter-stage data
├── prompts/
│   ├── research_prompt.txt    # Stage 1 system prompt
│   └── script_prompt.txt      # Stage 2 system prompt
├── tests/
│   ├── fixtures/
│   │   ├── sample_brief.json  # Hardcoded research brief for Stage 2 testing
│   │   └── sample_script.json # Hardcoded script for Stage 3 testing
│   ├── test_research_agent.py
│   ├── test_script_generator.py
│   ├── test_audio_assembler.py
│   └── test_metadata_packager.py
└── docs/
    ├── architecture.md        # Detailed system design notes
    └── api_notes.md           # ElevenLabs and Tavily API quirks
```

---

## Tech Stack

| Layer | Tool |
|---|---|
| LLM | Anthropic Claude `claude-sonnet-4-5` |
| Agent Orchestration | LangChain |
| Web Search | Tavily API |
| Text-to-Speech | ElevenLabs `eleven_turbo_v2` |
| Audio Assembly | pydub + ffmpeg |
| HTTP | requests |
| Env Management | python-dotenv |
| Testing | pytest |
| Linting | ruff |

---

## Environment Variables

All secrets live in `.env` at the project root. Never commit `.env`. Always reference `.env.example` for the full list.

```
ANTHROPIC_API_KEY=
ELEVENLABS_API_KEY=
TAVILY_API_KEY=
ELEVENLABS_VOICE_ID_HOST_A=
ELEVENLABS_VOICE_ID_HOST_B=
BUZZSPROUT_API_KEY=          # optional — for automated upload
BUZZSPROUT_PODCAST_ID=       # optional
```

Load in every module with:

```python
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY")
```

---

## Pipeline Stages

### Stage 1 — `research_agent.py`

**Purpose:** Research a topic and produce a structured brief.

**Input:**
```python
topic: str  # e.g. "The impact of AI on newsroom employment"
```

**Output:**
```json
{
  "topic": "string",
  "key_angles": ["string"],
  "facts_and_stats": ["string"],
  "expert_perspectives": ["string"],
  "controversy_or_nuance": "string",
  "sources": ["url"]
}
```

**Implementation notes:**
- Use LangChain's `create_react_agent` with `TavilySearchResults(max_results=5)`
- Run at least 3 distinct searches per topic to ensure source diversity
- Deduplicate sources before returning
- If Tavily returns no results, raise `ResearchError` — do not silently pass empty data downstream
- Validate output against the JSON schema in `validators.py` before returning

---

### Stage 2 — `script_generator.py`

**Purpose:** Transform a research brief into a two-host podcast script.

**Input:** Research brief JSON from Stage 1

**Output:**
```json
{
  "title": "string",
  "duration_estimate": "string",
  "segments": [
    {
      "segment": "intro | main | interview | wrap",
      "turns": [
        { "speaker": "HOST_A", "text": "string" },
        { "speaker": "HOST_B", "text": "string" }
      ]
    }
  ]
}
```

**Host personas (enforce in prompt):**
- `HOST_A` — warm, curious, drives narrative, asks questions
- `HOST_B` — analytical, slightly skeptical, adds context and pushback

**Implementation notes:**
- Use a single Claude API call with the full research brief in the user message
- Instruct the model to return ONLY valid JSON — no preamble, no markdown fences
- Strip any accidental markdown fences before parsing: `text.strip().strip("```json").strip("```")`
- Target script length: 1,800–2,500 words across all turns (~18–25 min episode)
- Validate output JSON schema before returning
- Prompts live in `prompts/script_prompt.txt` — load from file, do not hardcode in source

---

### Stage 3 — `audio_assembler.py`

**Purpose:** Synthesize each speaker turn via ElevenLabs and assemble the final episode.

**Input:** Script JSON from Stage 2

**Output:** `episodes/episode_{n}.mp3`

**Implementation notes:**
- Synthesize each `turn.text` individually — do not batch turns together
- Write each clip to a temp file in `/tmp/podcraft/`, load with pydub, then delete
- Insert `AudioSegment.silent(duration=300)` between speaker turns
- Insert `AudioSegment.silent(duration=800)` between segments
- Background music: load from `music/` directory, loop if shorter than episode, reduce to -18dB under dialogue
- Normalize the final mix before export: `final = final.normalize()`
- Export at 192k bitrate: `final.export(path, format="mp3", bitrate="192k")`
- ffmpeg must be on PATH — check at startup and raise `EnvironmentError` if missing
- **Cost control:** During development, limit TTS calls to the first 2 turns of a script using a `dev_mode=True` flag in `run_pipeline()`

---

### Stage 4 — `metadata_packager.py`

**Purpose:** Generate RSS-compatible metadata and write the episode sidecar file.

**Input:** Script JSON + episode number

**Output:** `episodes/episode_{n}_meta.json`

```json
{
  "title": "string",
  "episode": 1,
  "published": "ISO 8601 datetime",
  "duration_estimate": "string",
  "description": "string",
  "tags": ["string"],
  "chapters": ["intro", "main", "wrap"],
  "mp3_path": "episodes/episode_1.mp3"
}
```

**Implementation notes:**
- Generate a 2–3 sentence description using a brief Claude API call — do not use the full script
- Tags should be generated by Claude based on topic and talking points (aim for 5–8 tags)
- If `BUZZSPROUT_API_KEY` is set, attempt automated upload after writing sidecar; log success/failure but do not raise on upload failure

---

## Entry Point — `pipeline.py`

```python
def run_pipeline(topic: str, episode_num: int, dev_mode: bool = False) -> dict:
    """
    Runs all four pipeline stages in sequence.
    
    Args:
        topic: The subject to research and produce an episode about.
        episode_num: Episode number used for output file naming.
        dev_mode: If True, limits TTS to first 2 turns to conserve API credits.
    
    Returns:
        dict with keys: brief, script, mp3_path, meta_path
    """
```

- Log the start and completion of each stage with elapsed time
- If any stage raises an exception, log it with full traceback and halt — do not attempt to continue with bad data
- Save intermediate outputs (brief, script) to `episodes/episode_{n}_brief.json` and `episodes/episode_{n}_script.json` so stages can be re-run independently during development

---

## Data Flow

```
topic (str)
    │
    ▼
[Stage 1] research_agent.py
    │  brief.json
    ▼
[Stage 2] script_generator.py
    │  script.json
    ▼
[Stage 3] audio_assembler.py
    │  episode_N.mp3
    ▼
[Stage 4] metadata_packager.py
    │  episode_N_meta.json
    ▼
episodes/ directory
```

---

## Coding Standards

- **Style:** Follow PEP 8. Use `ruff` for linting (`ruff check src/`).
- **Type hints:** All function signatures must include type hints.
- **Docstrings:** Every public function needs a one-line docstring minimum.
- **Error handling:** Never use bare `except:`. Always catch specific exceptions.
- **No hardcoded secrets:** All API keys via environment variables only.
- **No print statements:** Use the logger from `utils/logger.py` for all output.
- **JSON parsing:** Always wrap `json.loads()` in try/except and raise a descriptive error on failure.
- **Temp files:** Always clean up temp files in a `finally` block.
- **Constants:** Define voice IDs, model names, and bitrate at the top of each module as constants — never inline magic strings.

---

## Testing Strategy

- **Always test stages in isolation first** using fixture files in `tests/fixtures/`
- `sample_brief.json` — use to test Stage 2 without calling Tavily
- `sample_script.json` — use to test Stage 3 without calling Claude or Tavily
- Run tests with: `pytest tests/ -v`
- Before running any full end-to-end pipeline test, confirm API keys are set and dev_mode is True

---

## Build Order

Always build and validate each stage independently before connecting them.

1. **Stage 2 first** — load `sample_brief.json`, confirm valid script JSON output
2. **Stage 1** — confirm research brief validates against schema, feeds Stage 2 cleanly
3. **Stage 3** — use `sample_script.json`, test with `dev_mode=True` (2 turns only)
4. **Stage 4** — confirm sidecar JSON writes correctly alongside the mp3
5. **Full pipeline** — run end-to-end with `dev_mode=True`, then a single full episode

---

## Known Constraints & Gotchas

- `pydub` requires `ffmpeg` on PATH — always check at startup
- ElevenLabs `eleven_turbo_v2` has a 5,000 character limit per request — split long turns if needed
- Claude API responses may include markdown code fences even when instructed not to — always strip before parsing
- Tavily free tier: 1,000 searches/month — be conservative during development
- ElevenLabs free tier: 10,000 characters/month — use `dev_mode=True` religiously during development
- `pydub` `AudioSegment.from_mp3()` will silently fail on corrupt files — always check file size > 0 before loading
- RSS feeds expect duration in `HH:MM:SS` format — convert from pydub's milliseconds before writing metadata

---

## Useful Commands

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run linter
ruff check src/

# Run all tests
pytest tests/ -v

# Run pipeline (dev mode)
python src/pipeline.py --topic "AI in journalism" --episode 1 --dev

# Run pipeline (full)
python src/pipeline.py --topic "AI in journalism" --episode 1

# Start the web API (FastAPI + uvicorn)
python server.py

# Install frontend dependencies (first time)
cd web && npm install

# Start the frontend dev server (run alongside the API)
cd web && npm run dev

# Build the frontend for production
cd web && npm run build
```

> The web UI runs at `http://localhost:5173` (dev) and proxies all `/api` and `/episodes`
> requests to the FastAPI server at `http://localhost:8000`. Start both servers to use the UI.

---

## Academic Context

This project satisfies a 3-credit independent study (MCOM 4900) at West Texas A&M University under the supervision of Randy Ray, Director of Broadcast Engineering. The academic paper accompanying this project engages the following theoretical frameworks:

- **Gatekeeping theory** (Shoemaker & Vos, 2009) — applied to Stage 1's editorial filtering
- **Agenda-setting theory** (McCombs & Shaw, 1972) — applied to Stage 2's topic framing
- **Production workflow theory** (McLeish & Link, 2016) — applied to overall pipeline structure
- **Parasocial interaction** (Horton & Wohl, 1956) — applied to host persona design in Stage 2

Code decisions that relate to these frameworks should be noted with a `# THEORY:` comment for reference during paper writing.

# podcraft-ai — Project Context

> End-to-end AI pipeline that researches a topic, writes a two-host script, synthesizes voices, and exports a broadcast-ready podcast episode.

---

## Tech Stack

| Layer | Tool / Library |
|---|---|
| Language | Python 3.11+ |
| LLM | Anthropic Claude (`claude-sonnet-4-20250514`) |
| Agent Orchestration | LangChain or CrewAI |
| Web Search | Tavily API (free tier) |
| Text-to-Speech | ElevenLabs API (`eleven_turbo_v2`) |
| Audio Assembly | pydub + ffmpeg |
| Metadata / Distribution | JSON + Buzzsprout or Anchor RSS |
| Version Control | Git / GitHub |

---

## Pipeline Stages

### Stage 1 — Topic Research Agent
- Input: user-supplied topic string
- An agentic LLM uses Tavily web search tools to gather current, credible information
- Agent runs multiple searches, deduplicates sources, synthesizes key angles
- Output: structured JSON research brief containing talking points, facts, stats, and suggested perspectives

### Stage 2 — Script Generation
- Input: research brief JSON from Stage 1
- A second LLM call transforms the brief into a two-host conversational podcast script
- HOST_A persona: warm and curious
- HOST_B persona: analytical and slightly skeptical
- Prompt engineering enforces tone, word count targets, and journalistic balance
- Output: structured JSON with speaker turns, segment labels, title, and duration estimate

### Stage 3 — Voice Synthesis & Audio Assembly
- Input: script JSON from Stage 2
- Each speaker turn is sent to ElevenLabs TTS with a unique voice ID per host
- Audio clips are assembled in order using pydub
- 300ms silence padding inserted between speaker turns
- Background music track (royalty-free) ducked under dialogue and overlaid
- Final mix normalized and exported
- Output: broadcast-ready `.mp3` episode file at 192k bitrate

### Stage 4 — Metadata & Distribution Package
- Input: script JSON + episode number
- Generates RSS-compatible metadata: title, description, publish date, chapter markers, tags
- Metadata written to a `.json` sidecar file alongside the `.mp3`
- Optional: automated upload to Buzzsprout or Anchor via API
- Output: episode `.mp3` + `_meta.json` sidecar file

---

## Entry Point

```python
run_pipeline(topic: str, episode_num: int)
```

Executes all four stages in sequence and writes outputs to the `episodes/` directory.

---

## Build Order

1. **Stage 2 first** — hardcode a fake research brief, validate the script JSON structure
2. **Stage 1** — plug in the research agent so briefs are generated dynamically
3. **Stage 3** — TTS and audio assembly; test with short clips to manage API costs
4. **Stage 4** — metadata packaging; straightforward JSON and string formatting

---

## API Cost Estimates (per episode)

| Service | Free Tier | Per-Episode Cost (paid) |
|---|---|---|
| Tavily Search | 1,000 searches/month | ~$0.00 |
| Claude API | Pay as you go | ~$0.05–0.15 |
| ElevenLabs TTS | 10,000 chars/month | ~$0.10–0.30 |
| Buzzsprout Hosting | 2 hrs/month free | $0 (free tier) |

**Estimated total per episode: under $0.50**

---

## Environment Variables Required

```
ANTHROPIC_API_KEY=
ELEVENLABS_API_KEY=
TAVILY_API_KEY=
ELEVENLABS_VOICE_ID_HOST_A=
ELEVENLABS_VOICE_ID_HOST_B=
```

---

## Key Constraints

- All LLM outputs that feed the next stage must be valid, parseable JSON
- TTS is the most API-cost-sensitive stage — test with short clips during development
- ffmpeg must be installed and available on PATH for pydub to function
- Royalty-free music tracks must be sourced before Stage 3 development begins

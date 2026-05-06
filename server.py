"""FastAPI web server — REST API + SSE log streaming for the podcraft-ai web UI."""

import json
import logging
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Generator

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.utils.logger import logger

app = FastAPI(title="PodCraft AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EPISODES_DIR = Path(__file__).parent / "episodes"
EPISODES_DIR.mkdir(exist_ok=True)

# Mount episodes dir so mp3s are streamable at /episodes/<filename>
app.mount("/episodes", StaticFiles(directory=str(EPISODES_DIR)), name="episodes")

# In-memory run registry: run_id -> {"status": str, "log_queue": Queue}
_runs: dict[str, dict[str, Any]] = {}


# ── Models ────────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    topic: str
    episode_num: int
    dev_mode: bool = False


# ── Episode endpoints ─────────────────────────────────────────────────────────

@app.get("/api/episodes")
def list_episodes() -> list[dict[str, Any]]:
    """Return all episodes that have a sidecar meta JSON."""
    episodes = []
    for meta_file in sorted(EPISODES_DIR.glob("*_meta.json")):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            # Attach a streamable URL for the mp3
            mp3_name = Path(meta.get("mp3_path", "")).name
            mp3_path = EPISODES_DIR / mp3_name
            meta["mp3_url"] = f"/episodes/{mp3_name}" if mp3_path.exists() else None
            episodes.append(meta)
        except (json.JSONDecodeError, OSError):
            continue
    # Newest first
    episodes.sort(key=lambda e: e.get("published", ""), reverse=True)
    return episodes


# ── Pipeline run endpoints ────────────────────────────────────────────────────

class _QueueHandler(logging.Handler):
    """Forwards log records into a queue so SSE can stream them."""

    def __init__(self, q: queue.Queue) -> None:
        super().__init__()
        self._q = q

    def emit(self, record: logging.LogRecord) -> None:
        self._q.put(self.format(record))


def _run_pipeline_thread(run_id: str, topic: str, episode_num: int, dev_mode: bool) -> None:
    """Execute run_pipeline in a background thread, feeding logs into the run's queue."""
    run = _runs[run_id]
    q: queue.Queue = run["log_queue"]

    handler = _QueueHandler(q)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)

    try:
        run["status"] = "running"
        from src.pipeline import run_pipeline
        result = run_pipeline(topic=topic, episode_num=episode_num, dev_mode=dev_mode)
        run["status"] = "done"
        run["result"] = result
        q.put("__DONE__")
    except Exception as exc:
        run["status"] = "error"
        run["error"] = str(exc)
        q.put(f"ERROR: {exc}")
        q.put("__DONE__")
    finally:
        logger.removeHandler(handler)


@app.post("/api/pipeline/run")
def start_pipeline(req: RunRequest) -> dict[str, str]:
    """Start a pipeline run and return its run_id."""
    run_id = str(uuid.uuid4())
    _runs[run_id] = {
        "status": "pending",
        "log_queue": queue.Queue(),
        "result": None,
        "error": None,
    }
    t = threading.Thread(
        target=_run_pipeline_thread,
        args=(run_id, req.topic, req.episode_num, req.dev_mode),
        daemon=True,
    )
    t.start()
    return {"run_id": run_id}


@app.get("/api/pipeline/run/{run_id}/stream")
def stream_logs(run_id: str) -> StreamingResponse:
    """SSE endpoint — streams log lines for a given run until it completes."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found.")

    def event_generator() -> Generator[str, None, None]:
        run = _runs[run_id]
        q: queue.Queue = run["log_queue"]
        while True:
            try:
                line = q.get(timeout=30)
            except queue.Empty:
                # Send a keepalive comment so the connection stays open
                yield ": keepalive\n\n"
                continue
            if line == "__DONE__":
                status = run["status"]
                yield f"data: __STATUS__{status}\n\n"
                break
            yield f"data: {line}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/pipeline/run/{run_id}/status")
def run_status(run_id: str) -> dict[str, Any]:
    """Return the current status of a run."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found.")
    run = _runs[run_id]
    return {"run_id": run_id, "status": run["status"], "error": run.get("error")}


# ── Dev entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

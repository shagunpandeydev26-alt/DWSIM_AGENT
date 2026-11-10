"""FastAPI backend for the DWSIM agent web UI."""
from __future__ import annotations

import os
import threading

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import AgentSession, DEFAULT_MODELS, MAX_STEPS
from .demo_mode import run_demo
from pathlib import Path

app = FastAPI(title="DWSIM Agentic Flowsheet Generator")

STATIC_DIR = Path(__file__).resolve().parent.parent / "web"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class RunRequest(BaseModel):
    prompt: str
    model: str = "gemini-3.7-flash"


@app.get("/")
def index() -> HTMLResponse:
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>DWSIM Agent</h1><p>web/index.html missing</p>")


@app.get("/api/models")
def models() -> dict:
    all_models = ["demo (no LLM — template matching)"] + DEFAULT_MODELS
    return {"models": all_models, "default": os.environ.get("GEMINI_MODEL", DEFAULT_MODELS[0])}


@app.get("/api/health")
def health() -> dict:
    key = os.environ.get("GEMINI_API_KEY", "")
    return {
        "ok": True,
        "gemini_key_set": bool(key and key != "your-key-here"),
        "dwsim_path": os.environ.get("DWSIM_PATH",
                                     os.path.join(os.environ.get("LOCALAPPDATA", ""), "DWSIM")),
    }


@app.post("/api/run")
def run(req: RunRequest) -> dict:
    if not req.prompt.strip():
        raise HTTPException(400, "prompt is empty")

    events: list[dict] = []
    lock = threading.Lock()

    def on_event(kind: str, data: dict) -> None:
        with lock:
            events.append({"kind": kind, **data})

    if req.model.startswith("demo"):
        result = run_demo(req.prompt, on_event=on_event)
    else:
        try:
            session = AgentSession(model=req.model)
        except RuntimeError as e:
            raise HTTPException(500, str(e))
        result = session.run(req.prompt, on_event=on_event)

    result["events"] = events
    result["prompt"] = req.prompt
    return JSONResponse(result)

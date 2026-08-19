"""FastAPI backend: exposes the agent as an API for the UI and the eval runner."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..graph import peek_run, resume_run, start_run
from ..memory.stores import sqlite_store, vector_store

app = FastAPI(title="ProductPilot API", version="0.1.0")


class RunRequest(BaseModel):
    pm_input: str
    source_paths: list[str] = []
    org_name: str = ""


class ResumeRequest(BaseModel):
    thread_id: str
    resume: dict


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "memory_prds": len(sqlite_store().list_prds(1000)),
        "vector_docs": vector_store().count(),
        "backend": vector_store().backend,
    }


@app.post("/run")
def run(req: RunRequest) -> dict:
    if not req.pm_input.strip():
        raise HTTPException(400, "pm_input is required")
    thread = start_run(req.pm_input, req.source_paths, req.org_name)
    return {"thread_id": thread, **peek_run(thread)}


@app.post("/resume")
def resume(req: ResumeRequest) -> dict:
    return resume_run(req.thread_id, req.resume)


@app.get("/state/{thread_id}")
def state(thread_id: str) -> dict:
    from ..graph import GRAPH

    snap = GRAPH.get_state({"configurable": {"thread_id": thread_id}})
    if snap is None:
        raise HTTPException(404, "thread not found")
    return {"values": snap.values, "next": [n for n in snap.next]}


@app.get("/prds")
def prds() -> dict:
    return {"prds": sqlite_store().list_prds(50)}


@app.get("/prds/{prd_id}")
def prd(prd_id: int) -> dict:
    record = sqlite_store().get_prd(prd_id)
    if record is None:
        raise HTTPException(404, "prd not found")
    return record


@app.get("/memory/search")
def memory_search(q: str, k: int = 5) -> dict:
    return {"hits": vector_store().search(q, k=k)}


@app.get("/memory/decisions")
def decisions(q: str = "") -> dict:
    return {"decisions": sqlite_store().search_decisions(q) if q else []}
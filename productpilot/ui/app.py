"""Streamlit UI — renders the HITL checkpoints (clarification, synthesis approval,
PRD approval) as live widgets and drives the LangGraph state machine."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from productpilot import config
from productpilot.graph import GRAPH, new_thread_id, peek_run, resume_run, start_run
from productpilot.memory.stores import sqlite_store, vector_store

st.set_page_config(page_title="ProductPilot", page_icon="🛫", layout="wide")

DATA = config.SOURCES_DIR


# ---------------------------------------------------------------- session helpers

def _snapshot() -> dict | None:
    return st.session_state.get("snapshot")


def _set_snapshot(snap: dict | None) -> None:
    st.session_state["snapshot"] = snap


def _poll(thread: str) -> None:
    _set_snapshot(peek_run(thread))


def _resume(resume: dict) -> None:
    thread = st.session_state["thread"]
    out = resume_run(thread, resume)
    snap = {"state": out["state"], "interrupt": out["interrupt"], "finished": out["interrupt"] is None}
    _set_snapshot(snap)
    st.rerun()


def _start() -> None:
    files = st.session_state.get("selected_sources", [])
    uploads = st.session_state.get("uploaded_files", [])
    paths = [str(DATA / f) for f in files]
    for up in uploads:
        target = config.DB_DIR / "uploads" / up.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(up.getvalue())
        paths.append(str(target))
    thread = start_run(st.session_state["pm_input"], paths, st.session_state.get("org_name", ""))
    st.session_state["thread"] = thread
    _poll(thread)


def _reset() -> None:
    st.session_state.pop("thread", None)
    _set_snapshot(None)
    st.rerun()


# ------------------------------------------------------------------ sidebar

with st.sidebar:
    st.title("ProductPilot")
    st.caption("Track B · Knowledge Agent — Hackathon 2026")
    st.divider()
    st.write(f"**Mode:** `{'mock (offline)' if config.MOCK else 'live LLM'}`")
    st.write(f"**Memory:** {config.SQLITE_PATH.name} + {vector_store().backend} index")
    st.write(f"**Vector docs:** {vector_store().count()} · **PRDs:** {len(sqlite_store().list_prds(1000))}")
    st.divider()
    st.subheader("Recent PRDs")
    for r in sqlite_store().list_prds(8):
        st.markdown(f"- **#{r['id']}** {r['title'][:48]} — critic {r['critic_overall']}")
    st.divider()
    if st.button("New session", use_container_width=True):
        _reset()

# ------------------------------------------------------------------ main

st.header("The PM's work, done by an agent that thinks.")

snap = _snapshot()
thread = st.session_state.get("thread")

if thread is None:
    st.markdown(
        "ProductPilot ingests your raw feedback, researches the market, sizes opportunities with "
        "sourced RICE, writes a PRD, and criticizes it — with **your approval** at two checkpoints."
    )
    st.text_area("PM request", key="pm_input", height=110,
                 placeholder="e.g. churn is high in month 2 — investigate and propose a fix")
    st.text_input("Org name", key="org_name", placeholder="Metrica")
    st.multiselect(
        "Raw sources (sample data)", [p.name for p in sorted(DATA.iterdir())],
        key="selected_sources",
    )
    st.file_uploader("…or upload your own (CSV / JSON / MD)", type=["csv", "json", "jsonl", "md", "txt"],
                     accept_multiple_files=True, key="uploaded_files")
    if st.button("Run ProductPilot", type="primary", use_container_width=True):
        if not st.session_state.get("pm_input", "").strip():
            st.warning("Describe the request first.")
        else:
            _start()
else:
    st.button("↺ Reset", on_click=_reset)
    st.caption(f"thread `{thread}`")

if snap is None:
    st.stop()

state = snap["state"]
interrupt = snap["interrupt"]

if interrupt is not None:
    kind = interrupt.get("type")
    st.subheader(f"⏸ Human-in-the-loop — {kind}")
    if kind == "clarification":
        st.info(interrupt.get("question"))
        answer = st.text_input("Your answer", key="clar_ans")
        if st.button("Continue", type="primary"):
            if answer.strip():
                _resume({"answer": answer})
    elif kind == "synthesis_approval":
        left, right = st.columns(2)
        with left:
            st.markdown("**Research synthesis**")
            st.markdown(state.get("synthesis", ""))
        with right:
            st.markdown("**Themes**")
            for t in state.get("themes", []):
                st.markdown(f"- {t.get('name')} — {t.get('frequency')} mentions ({t.get('sentiment')})")
            st.markdown("**RICE options**")
            for o in state.get("options", []):
                st.markdown(
                    f"- **{o.get('name')}** · RICE {o.get('rice')} · confidence **{o.get('confidence_label')}**"
                )
            for c in state.get("contradictions", []):
                st.warning(f"Contradiction: {c.get('name')} — {c.get('detail')}")
            if state.get("injection_flags"):
                st.error(f"{len(state.get('injection_flags'))} prompt-injection attempt(s) quarantined")
        st.markdown("—")
        feedback = st.text_area("Feedback (only if you want revisions)", key="syn_fb", height=80)
        c1, c2 = st.columns(2)
        if c1.button("Approve synthesis → draft PRD", type="primary", use_container_width=True):
            _resume({"approved": True, "feedback": ""})
        if c2.button("Reject & revise", use_container_width=True):
            _resume({"approved": False, "feedback": feedback or "Tighten the synthesis."})
    elif kind == "prd_approval":
        left, right = st.columns([3, 2])
        with left:
            st.markdown(state.get("prd_draft", ""))
        with right:
            st.markdown("**Critic rubric scores**")
            scores = state.get("critic_scores", {})
            for dim in config.RUBRIC_DIMENSIONS:
                st.progress(min(float(scores.get(dim, 0)) / 10, 1.0), text=f"{dim}: {scores.get(dim, '—')}")
            st.metric("Overall", scores.get("overall", "—"), delta=None)
            if state.get("critic_feedback"):
                st.markdown("**Critic feedback**")
                for f in state["critic_feedback"][:6]:
                    st.markdown(f"- {f}")
        feedback = st.text_area("Feedback (if you reject)", key="prd_fb", height=80)
        c1, c2 = st.columns(2)
        if c1.button("Approve PRD → commit to memory", type="primary", use_container_width=True):
            _resume({"approved": True, "feedback": ""})
        if c2.button("Reject & revise", use_container_width=True):
            _resume({"approved": False, "feedback": feedback or "Address the critic's weakest dimension."})
    st.stop()

# ---------------------------------------------------------------- finished state

st.success("Committed to org memory.")
c1, c2 = st.columns([3, 2])
with c1:
    st.markdown("### PRD")
    st.markdown(state.get("prd_draft", ""))
with c2:
    st.markdown("### Critic")
    scores = state.get("critic_scores", {})
    st.metric("Overall rubric score", scores.get("overall", "—"))
    for dim in config.RUBRIC_DIMENSIONS:
        st.progress(min(float(scores.get(dim, 0)) / 10, 1.0), text=f"{dim}: {scores.get(dim, '—')}")
    st.markdown("### RICE options")
    for o in state.get("options", []):
        st.markdown(f"- **{o.get('name')}** · RICE {o.get('rice')} · {o.get('confidence_label')} confidence")
    st.markdown(f"PRD id: `#{state.get('prd_id')}` · status `{state.get('status')}`")

st.divider()
with st.expander("Reasoning trace (sources → decisions)"):
    trace = state.get("trace", {})
    st.json(json.dumps(trace, indent=2, default=str) if trace else "{}")
with st.expander("Org memory — semantic search test"):
    q = st.text_input("Search memory", key="mem_q", value=state.get("pm_input", ""))
    if q:
        for hit in vector_store().search(q, k=6):
            st.markdown(f"- **{hit['title']}** ({hit['doc_type']}, score {hit['score']}) — {hit['text'][:120]}…")

st.caption("ProductPilot · 5 agents · LangGraph · critic loop ≤2 · 100% traceable")
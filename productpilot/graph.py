"""ProductPilot graph — the LangGraph state machine.

Flow:
  START -> planner -> (vague?) clarify_gate (interrupt) -> [researcher, analyst] (parallel)
       -> synthesize -> synthesis_gate (interrupt, revise <=2)
       -> writer -> critic (rubric loop <=2) -> prd_gate (interrupt)
       -> finalize (memory write) -> END

Human-in-the-loop is implemented with interrupt(); resumes arrive via Command(resume=...).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send

from . import config
from .agents import analyst, critic, planner, researcher, writer
from .memory.stores import sqlite_store, vector_store
from .state import ProductPilotState

CHECKPOINTER = MemorySaver()


# ------------------------------------------------------------------- nodes

def planner_node(state: dict) -> dict:
    return planner.run(state)


def clarify_gate(state: dict) -> dict:
    """Interrupt: ask the PM the clarifying question; resume carries the answer."""
    if state.get("clarification_answer"):
        return {"status": "clarified"}
    answer = interrupt_payload(
        {
            "type": "clarification",
            "question": state.get("clarifying_question", ""),
            "message": "The request is too vague to research safely. Please provide scope.",
        }
    )
    if isinstance(answer, str):
        answer_text = answer
    else:
        answer_text = str(answer.get("answer", ""))
    return {
        "clarification_answer": answer_text,
        "pm_input": f"{state.get('pm_input', '')}\n[Clarification] {answer_text}",
        "status": "clarified",
    }


def researcher_node(state: dict) -> dict:
    return researcher.run(state)


def analyst_node(state: dict) -> dict:
    return analyst.run(state)


def synthesize_node(state: dict) -> dict:
    """Merge research + analysis into a single PM-readable synthesis document."""
    revisions = state.get("synthesis_revisions", 0)
    base = state.get("synthesis", "")
    feedback = state.get("pm_synthesis_feedback", "")
    doc = base
    if revisions > 0:
        doc = f"{base}\n\n## Revision {revisions} — PM feedback incorporated\n{feedback}"
    return {"synthesis_revisions": revisions + 1, "status": "synthesis_ready"}


def synthesis_gate(state: dict) -> dict:
    """Interrupt: PM approves the research synthesis before any PRD drafting."""
    if state.get("synthesis_revisions", 0) > config.MAX_SYNTHESIS_REVISIONS:
        return {"status": "synthesis_accepted", "synthesis_approved": True}
    decision = interrupt_payload(
        {
            "type": "synthesis_approval",
            "synthesis": state.get("synthesis", ""),
            "themes": state.get("themes", []),
            "options": state.get("options", []),
            "contradictions": state.get("contradictions", []),
            "memory_hits": state.get("memory_hits", []),
            "injection_flags": state.get("injection_flags", []),
        }
    )
    approved = decision.get("approved", True) if isinstance(decision, dict) else True
    feedback = decision.get("feedback", "") if isinstance(decision, dict) else ""
    if approved:
        return {"status": "synthesis_accepted", "synthesis_approved": True}
    return {
        "status": "synthesis_rejected",
        "pm_synthesis_feedback": feedback,
        "synthesis_approved": False,
    }


def writer_node(state: dict) -> dict:
    return writer.run(state)


def critic_node(state: dict) -> dict:
    return critic.run(state)


def prd_gate(state: dict) -> dict:
    """Interrupt: PM approves the final PRD before commit to memory."""
    if state.get("prd_feedback_revisions", 0) > config.MAX_PRD_FEEDBACK_REVISIONS:
        return {"status": "prd_approved", "prd_approved": True}
    decision = interrupt_payload(
        {
            "type": "prd_approval",
            "prd_draft": state.get("prd_draft", ""),
            "critic_scores": state.get("critic_scores", {}),
        }
    )
    approved = decision.get("approved", True) if isinstance(decision, dict) else True
    feedback = decision.get("feedback", "") if isinstance(decision, dict) else ""
    if approved:
        return {"status": "prd_approved", "prd_approved": True}
    return {
        "status": "prd_rejected",
        "pm_prd_feedback": feedback,
        "prd_feedback_revisions": state.get("prd_feedback_revisions", 0) + 1,
        "prd_approved": False,
    }


def finalize_node(state: dict) -> dict:
    """Write PRD + decision + trace to SQLite and the vector index."""
    trace = {
        "pm_input": state.get("pm_input", ""),
        "org_name": state.get("org_name", ""),
        "request_type": state.get("request_type", "standard"),
        "clarification": state.get("clarifying_question", "") or None,
        "clarification_answer": state.get("clarification_answer", "") or None,
        "source_paths": state.get("source_paths", []),
        "themes": state.get("themes", []),
        "options": state.get("options", []),
        "contradictions": state.get("contradictions", []),
        "compliance_dependencies": state.get("compliance_dependencies", []),
        "memory_hits": state.get("memory_hits", []),
        "injection_flags": state.get("injection_flags", []),
        "critic_history": {"scores": state.get("critic_scores", {}), "feedback": state.get("critic_feedback", [])},
        "revision_passes": state.get("revisions", 0),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "graph": "langgraph",
    }

    title = _first_heading(state.get("prd_draft", "")) or state.get("brief") or "Untitled PRD"
    prd_id = sqlite_store().save_prd(
        title=title,
        pm_input=state.get("pm_input", ""),
        prd_markdown=state.get("prd_draft", ""),
        critic_scores=state.get("critic_scores", {}),
        status=state.get("status", "committed"),
        trace=trace,
        org_name=state.get("org_name", ""),
        decisions=state.get("options", []),
    )
    vector_store().index(
        text=state.get("prd_draft", ""),
        doc_type="prd",
        title=title,
        source=f"sqlite://prd/{prd_id}",
        meta={"pm_input": state.get("pm_input", ""), "critic_overall": state.get("critic_scores", {}).get("overall")},
    )
    if state.get("synthesis"):
        vector_store().index(
            text=state.get("synthesis", ""),
            doc_type="synthesis",
            title=f"Synthesis — {title}",
            source=f"sqlite://prd/{prd_id}",
        )
    return {
        "status": "committed",
        "trace": trace,
        "prd_id": prd_id,
        "thread_id": state.get("__thread_id", ""),
    }


def _first_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


# ------------------------------------------------------------------ routing

def planner_router(state: dict) -> str:
    if state.get("needs_clarification") and not state.get("clarification_answer"):
        return "clarify_gate"
    return "researcher"


def clarify_router(state: dict) -> str:
    return "researcher"


def synthesis_router(state: dict) -> str:
    if (
        not state.get("synthesis_approved")
        and state.get("synthesis_revisions", 0) <= config.MAX_SYNTHESIS_REVISIONS
        and state.get("pm_synthesis_feedback")
    ):
        return "synthesize"
    return "writer"


def critic_router(state: dict) -> str:
    overall = state.get("critic_scores", {}).get("overall", 0)
    if overall < config.CRITIC_THRESHOLD and state.get("revisions", 0) < config.MAX_REVISIONS:
        return "writer"
    return "prd_gate"


def prd_router(state: dict) -> str:
    if not state.get("prd_approved") and state.get("prd_feedback_revisions", 0) <= config.MAX_PRD_FEEDBACK_REVISIONS:
        return "writer"
    return "finalize"


# ------------------------------------------------------------------ interrupt helper

def interrupt_payload(payload: dict):
    from langgraph.types import interrupt

    return interrupt(payload)


# ------------------------------------------------------------------ builder

def build_graph():
    g = StateGraph(ProductPilotState)
    g.add_node("planner", planner_node)
    g.add_node("clarify_gate", clarify_gate)
    g.add_node("researcher", researcher_node)
    g.add_node("analyst", analyst_node)
    g.add_node("synthesize", synthesize_node)
    g.add_node("synthesis_gate", synthesis_gate)
    g.add_node("writer", writer_node)
    g.add_node("critic", critic_node)
    g.add_node("prd_gate", prd_gate)
    g.add_node("finalize", finalize_node)

    g.add_edge(START, "planner")
    g.add_conditional_edges("planner", planner_router, {"clarify_gate": "clarify_gate", "researcher": "researcher"})
    g.add_conditional_edges("clarify_gate", clarify_router, {"researcher": "researcher"})
    g.add_edge("researcher", "analyst")
    g.add_edge("analyst", "synthesize")
    g.add_edge("synthesize", "synthesis_gate")
    g.add_conditional_edges("synthesis_gate", synthesis_router, {"synthesize": "synthesize", "writer": "writer"})
    g.add_edge("writer", "critic")
    g.add_conditional_edges("critic", critic_router, {"writer": "writer", "prd_gate": "prd_gate"})
    g.add_conditional_edges("prd_gate", prd_router, {"writer": "writer", "finalize": "finalize"})
    g.add_edge("finalize", END)
    return g.compile(checkpointer=CHECKPOINTER)


GRAPH = build_graph()


def _interrupt_payload_from_exc(exc: Exception) -> dict | None:
    """Best-effort adapter for legacy LangGraph interrupt exceptions.

    Older versions raised an exception that carried interrupt payload in `value`.
    Newer versions pause the thread without raising.
    """
    value = getattr(exc, "value", None)
    if value is None:
        return None
    values = value if isinstance(value, list) else [value]
    payload = values[0] if values else {}
    return payload if isinstance(payload, dict) else {}


def new_thread_id() -> str:
    return uuid.uuid4().hex[:16]


def run_with_auto_approval(
    pm_input: str,
    source_paths: list[str] | None = None,
    org_name: str = "",
    auto_answer: str = "The analytics product, new trial signups.",
    thread_id: str | None = None,
) -> tuple[dict, list[dict]]:
    """Drive the graph end-to-end, auto-resuming every HITL checkpoint (eval/CLI mode)."""
    thread = thread_id or new_thread_id()
    config_ = {"configurable": {"thread_id": thread}}
    initial = {
        "pm_input": pm_input,
        "source_paths": [source_paths] if isinstance(source_paths, str) else (source_paths or []),
        "org_name": org_name,
    }
    interrupts_seen: list[dict] = []
    resume = None
    while True:
        try:
            if resume is None:
                GRAPH.invoke(initial, config_)
            else:
                GRAPH.invoke(Command(resume=resume), config_)
        except Exception as exc:
            payload = _interrupt_payload_from_exc(exc)
            if payload is None:
                raise
            interrupts_seen.append(payload)
            resume = {"answer": auto_answer} if payload.get("type") == "clarification" else {"approved": True, "feedback": ""}
            continue
        payload = _pending_interrupt(thread)
        if payload is None:
            return GRAPH.get_state(config_).values, interrupts_seen
        interrupts_seen.append(payload)
        resume = {"answer": auto_answer} if payload.get("type") == "clarification" else {"approved": True, "feedback": ""}


def _pending_interrupt(thread: str) -> dict | None:
    """Return the interrupt payload waiting on the thread, if any."""
    config_ = {"configurable": {"thread_id": thread}}
    snap = GRAPH.get_state(config_)
    if not snap.next:
        return None
    tasks = list(snap.tasks)
    if tasks and getattr(tasks[0], "interrupts", None):
        return tasks[0].interrupts[0].value
    return None


def start_run(pm_input: str, source_paths: list[str], org_name: str = "") -> str:
    thread = new_thread_id()
    config_ = {"configurable": {"thread_id": thread}}
    GRAPH.invoke(
        {"pm_input": pm_input, "source_paths": source_paths, "org_name": org_name},
        config_,
    )
    return thread


def peek_run(thread: str) -> dict:
    """Snapshot of a paused/finished run (no resume)."""
    config_ = {"configurable": {"thread_id": thread}}
    snap = GRAPH.get_state(config_)
    return {"state": snap.values, "interrupt": _pending_interrupt(thread), "finished": not snap.next}


def resume_run(thread: str, resume: dict) -> dict:
    config_ = {"configurable": {"thread_id": thread}}
    try:
        GRAPH.invoke(Command(resume=resume), config_)
    except Exception as exc:
        payload = _interrupt_payload_from_exc(exc)
        if payload is None:
            raise
        return {"state": GRAPH.get_state(config_).values, "interrupt": payload}
    payload = _pending_interrupt(thread)
    return {"state": GRAPH.get_state(config_).values, "interrupt": payload, "finished": payload is None}
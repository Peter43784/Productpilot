"""Analyst — theme clustering, RAG recall, sourced RICE, contradiction detection,
compliance dependencies. Produces the research synthesis for PM approval.
"""
from __future__ import annotations

from .. import llm, prompts
from ..memory.stores import vector_store
from .planner import llm_json_payload


def run(state: dict) -> dict:
    model = llm.get_llm("analyst")

    memory_hits = []
    try:
        query = state.get("pm_input", "")
        if query:
            hits = vector_store().search(query, k=5)
            memory_hits = [
                {
                    "title": h["title"], "doc_type": h["doc_type"], "source": h["source"],
                    "score": h["score"], "snippet": h["text"][:400],
                }
                for h in hits
            ]
    except Exception:
        memory_hits = []

    payload = {
        "pm_input": state.get("pm_input", ""),
        "org_name": state.get("org_name", ""),
        "request_type": state.get("request_type", "standard"),
        "research_notes": state.get("research_notes", []),
        "web_results": state.get("web_results", []),
        "memory_hits": memory_hits,
        "pm_feedback": state.get("pm_synthesis_feedback", ""),
        "revision": state.get("synthesis_revisions", 0),
    }
    response = llm.ask_json(model, prompts.ANALYST, llm_json_payload(payload))
    parsed = response
    return {
        "themes": parsed.get("themes", []),
        "options": parsed.get("options", []),
        "contradictions": parsed.get("contradictions", []),
        "memory_hits": memory_hits,
        "compliance_dependencies": parsed.get("compliance_dependencies", []),
        "synthesis": parsed.get("synthesis_markdown", ""),
        "status": "analysis_done",
    }

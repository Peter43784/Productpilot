"""PRD Writer — builds the structured, spec-quality PRD from the approved synthesis."""
from __future__ import annotations

from .. import llm, prompts
from .planner import llm_json_payload


def run(state: dict) -> dict:
    model = llm.get_llm("writer")
    payload = {
        "pm_input": state.get("pm_input", ""),
        "org_name": state.get("org_name", ""),
        "request_type": state.get("request_type", "standard"),
        "synthesis": state.get("synthesis", ""),
        "themes": state.get("themes", []),
        "options": state.get("options", []),
        "contradictions": state.get("contradictions", []),
        "compliance_dependencies": state.get("compliance_dependencies", []),
        "memory_hits": state.get("memory_hits", []),
        "critic_feedback": state.get("critic_feedback", []),
        "pm_prd_feedback": state.get("pm_prd_feedback", ""),
        "revision": state.get("revisions", 0),
    }
    response = llm.ask(model, prompts.WRITER, llm_json_payload(payload))
    return {"prd_draft": response, "status": "drafted"}

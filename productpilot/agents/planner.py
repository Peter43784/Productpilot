"""Planner — classifies the PM request; routes vague asks to a clarification gate."""
from __future__ import annotations

from .. import llm, prompts


def run(state: dict) -> dict:
    model = llm.get_llm("planner")
    payload = {
        "pm_input": state.get("pm_input", ""),
        "org_name": state.get("org_name", ""),
        "source_count": len(state.get("source_paths", [])),
    }
    response = llm.ask_json(model, prompts.PLANNER, llm_json_payload(payload))
    parsed = response
    return {
        "needs_clarification": bool(parsed.get("needs_clarification", False)),
        "clarifying_question": parsed.get("question", ""),
        "request_type": parsed.get("request_type", "standard"),
        "brief": parsed.get("brief", ""),
        "status": "clarification_required" if parsed.get("needs_clarification") else "planning_done",
    }


def llm_json_payload(payload: dict) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)

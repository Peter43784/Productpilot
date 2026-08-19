"""Critic — scores drafts on the 7-point rubric (Haiku for cheap, strict evaluation)."""
from __future__ import annotations

from .. import llm, prompts
from .planner import llm_json_payload


def run(state: dict) -> dict:
    model = llm.get_llm("critic")
    payload = {
        "prd_draft": state.get("prd_draft", ""),
        "pm_input": state.get("pm_input", ""),
        "request_type": state.get("request_type", "standard"),
        "revision": state.get("revisions", 0),
    }
    response = llm.ask_json(model, prompts.CRITIC, llm_json_payload(payload))
    parsed = response
    scores = parsed.get("scores", {})
    scores["overall"] = parsed.get("overall", round(sum(scores.values()) / len(scores), 2) if scores else 0)
    return {
        "critic_scores": scores,
        "critic_feedback": parsed.get("feedback", []),
        "revisions": (state.get("revisions") or 0) + 1,
        "status": "critiqued",
    }

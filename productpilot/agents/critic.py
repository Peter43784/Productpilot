"""Critic — scores drafts on the 7-point rubric (Haiku for cheap, strict evaluation)."""
from __future__ import annotations

from .base import Agent
from .. import prompts


class CriticAgent(Agent):
    role = "critic"
    prompt = prompts.CRITIC
    
    def build_payload(self, state: dict) -> dict:
        return {
            "prd_draft": state.get("prd_draft", ""),
            "pm_input": state.get("pm_input", ""),
            "request_type": state.get("request_type", "standard"),
            "revision": state.get("revisions", 0),
        }
    
    def parse_response(self, response: dict, state: dict) -> dict:
        scores = response.get("scores", {})
        scores["overall"] = response.get("overall", round(sum(scores.values()) / len(scores), 2) if scores else 0)
        return {
            "critic_scores": scores,
            "critic_feedback": response.get("feedback", []),
            "revisions": (state.get("revisions") or 0) + 1,
            "status": "critiqued",
        }


critic = CriticAgent()
run = critic.run

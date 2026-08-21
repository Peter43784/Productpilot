"""Planner — classifies the PM request; routes vague asks to a clarification gate."""
from __future__ import annotations

from .base import Agent
from .. import prompts


class PlannerAgent(Agent):
    role = "planner"
    prompt = prompts.PLANNER
    
    def build_payload(self, state: dict) -> dict:
        return {
            "pm_input": state.get("pm_input", ""),
            "org_name": state.get("org_name", ""),
            "source_count": len(state.get("source_paths", [])),
        }
    
    def parse_response(self, response: dict, state: dict) -> dict:
        return {
            "needs_clarification": bool(response.get("needs_clarification", False)),
            "clarifying_question": response.get("question", ""),
            "request_type": response.get("request_type", "standard"),
            "brief": response.get("brief", ""),
            "status": "clarification_required" if response.get("needs_clarification") else "planning_done",
        }


planner = PlannerAgent()
run = planner.run

"""Shared graph state for the ProductPilot state machine."""
from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages  # noqa: F401  (kept for API parity)


def replace(left: list, right: list) -> list:
    return right


def last(left: str, right: str) -> str:
    return right


class ProductPilotState(TypedDict, total=False):
    # --- inputs ---
    pm_input: str
    source_paths: list[str]
    org_name: str
    request_type: str
    brief: str

    # --- clarification flow ---
    needs_clarification: bool
    clarifying_question: str
    clarification_answer: str

    # --- research ---
    research_notes: Annotated[list[dict], replace]
    web_results: Annotated[list[dict], replace]
    injection_flags: Annotated[list[dict], replace]

    # --- analysis ---
    themes: Annotated[list[dict], replace]
    options: Annotated[list[dict], replace]
    contradictions: Annotated[list[dict], replace]
    compliance_dependencies: Annotated[list[str], replace]
    memory_hits: Annotated[list[dict], replace]
    synthesis: str
    synthesis_revisions: int
    pm_synthesis_feedback: str

    # --- prd ---
    prd_draft: str
    critic_scores: dict
    critic_feedback: list[str]
    revisions: int
    pm_prd_feedback: str
    prd_feedback_revisions: int

    # --- output ---
    status: Annotated[str, last]
    trace: dict
    prd_id: int
    synthesis_approved: bool
    prd_approved: bool

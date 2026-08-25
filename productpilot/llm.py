"""LLM factory using Anthropic models."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from . import config

log = logging.getLogger("productpilot.llm")

VALID_ROLES = {"planner", "researcher", "analyst", "writer", "critic", "classifier"}


class LLMError(RuntimeError):
    pass


# --------------------------------------------------------------------------- helpers

def get_llm(role: str) -> Any:
    if role not in VALID_ROLES:
        raise LLMError(f"Unknown LLM role {role!r}; expected one of {sorted(VALID_ROLES)}")
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:
        raise LLMError(
            "langchain-anthropic not installed. Run `pip install -r requirements.txt`."
        ) from exc
    if not _api_key("ANTHROPIC_API_KEY"):
        raise LLMError(
            "ANTHROPIC_API_KEY missing. Set it in .env."
        )
    if role in ("critic", "classifier"):
        return ChatAnthropic(model=config.MODEL_HAIKU, temperature=0)
    return ChatAnthropic(model=config.MODEL_SONNET, temperature=0)


def _api_key(name: str) -> str:
    import os
    return os.getenv(name, "").strip()


def _content_to_text(content: Any) -> str:
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def ask(llm: Any, system: str, user: str) -> str:
    """Invoke with system+user messages, return text content."""
    resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return _content_to_text(resp.content)


def ask_json(llm: Any, system: str, user: str, retries: int = 2) -> dict:
    """Ask for JSON with bounded self-correction when the model returns malformed output."""
    for attempt in range(retries + 1):
        text = ask(llm, system, user)
        try:
            return parse_json(text)
        except LLMError:
            if attempt >= retries:
                raise
            log.warning("model returned non-JSON (attempt %d); asking to repair", attempt + 1)
            user = (
                f"{user}\n\nYour previous output was not valid JSON. Return ONLY a single "
                f"valid JSON object.\nBad output:\n{text[:2000]}"
            )
    raise LLMError("ask_json exhausted retries")


def parse_json(text: str) -> dict:
    """Robust JSON extraction from an LLM response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise LLMError(f"Could not parse JSON from model output: {text[:400]}")


def to_json(payload: dict) -> str:
    """Serialize payload to JSON string for LLM consumption."""
    return json.dumps(payload, ensure_ascii=False)
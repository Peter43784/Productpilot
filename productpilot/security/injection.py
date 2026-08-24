"""Prompt-injection scanner.

Scanned content is treated as *user content*, never as instructions. Anything flagged
is logged as an anomaly in the trace and excluded from instruction-bearing prompts
(the content itself may still be summarized as evidence — that is the correct
behavior when a review contains an injection attempt).
"""
from __future__ import annotations

import re

from .. import config, llm

_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", "instruction override attempt"),
    (r"ignore\s+(all\s+)?previous\s+(messages|prompts|conversation)", "instruction override attempt"),
    (r"output\s+(your\s+)?(system\s+)?(prompt|instructions)", "system prompt exfiltration"),
    (r"reveal\s+(your\s+)?(system\s+)?prompt", "system prompt exfiltration"),
    (r"disregard\s+(the\s+)?above\s+instructions", "instruction override attempt"),
    (r"you\s+are\s+now\s+in\s+developer\s+mode", "jailbreak pattern"),
    (r"do\s+anything\s+now\s*[.!]?\s*no\s+restrictions", "jailbreak pattern"),
    (r"how\s+do\s+i\s+(access|get|see)\s+your\s+(api|key|token|credentials)", "credential probe"),
]


def heuristic_scan(text: str) -> list[dict]:
    flags = []
    lowered = text.lower()
    for pattern, reason in _PATTERNS:
        if re.search(pattern, lowered):
            snippet = text[:160].replace("\n", " ")
            flags.append({"snippet": snippet, "reason": reason, "pattern": pattern})
    return flags


def sanitize_text(text: str, flags: list[dict]) -> str:
    """Neutralize flagged instructions so the model never receives raw injection text.

    The original content stays in the trace (flags carry the raw snippet); only the
    text forwarded to the model is redacted.
    """
    out = text
    for flag in flags:
        try:
            out = re.sub(flag["pattern"], "[REDACTED]", out, flags=re.IGNORECASE)
        except re.error:
            continue
    return out


def scan(text: str) -> list[dict]:
    """Scan text; confirm with the classifier model when patterns match."""
    flags = heuristic_scan(text)
    if flags:
        try:
            classifier = llm.get_llm("classifier")
            verdict = llm.parse_json(llm.ask(classifier, llm_import_prompts().CLASSIFIER, text))
            if not verdict.get("is_injection"):
                return []
            flags[0]["reason"] = verdict.get("reason", flags[0]["reason"])
        except Exception:
            pass
    return flags


def llm_import_prompts():
    from .. import prompts as _p

    return _p

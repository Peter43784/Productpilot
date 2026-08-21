"""LLM factory with an offline deterministic mock mode.

PRODUCTPILOT_MOCK=1 (default) uses MockLLM: rule-driven, deterministic responses so the
whole system runs without any API key (demo/CI). With keys set, real models are used:
Sonnet 4.5 for Planner/Researcher/Analyst/Writer, Haiku 3.5 for Critic + classifier.
"""
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


class MockResponse:
    def __init__(self, text: str):
        self.content = text

    def model_dump(self) -> dict:
        return {"content": self.content}


class MockLLM:
    """Deterministic stand-in. Dispatch is based on the system prompt marker."""

    def __init__(self, role: str):
        self.role = role

    def invoke(self, messages: list[Any]) -> MockResponse:
        system = next((m.content for m in messages if isinstance(m, SystemMessage)), "")
        user = next(
            (m.content for m in messages if isinstance(m, HumanMessage)), ""
        )
        try:
            return MockResponse(_mock_dispatch(self.role, system, str(user)))
        except Exception as exc:  # mock must never crash the graph
            log.warning("mock %s failed (%s) — returning degraded response", self.role, exc)
            return MockResponse(_mock_safe_response(self.role, exc))


# --------------------------------------------------------------------------- helpers

def get_llm(role: str) -> Any:
    if role not in VALID_ROLES:
        raise LLMError(f"Unknown LLM role {role!r}; expected one of {sorted(VALID_ROLES)}")
    if config.MOCK:
        return MockLLM(role)
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:
        raise LLMError(
            "langchain-anthropic not installed. Run `pip install -r requirements.txt`."
        ) from exc
    if not _api_key("ANTHROPIC_API_KEY"):
        raise LLMError(
            "ANTHROPIC_API_KEY missing. Set it in .env, or run mock mode with PRODUCTPILOT_MOCK=1."
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
    if isinstance(llm, MockLLM):
        return llm.invoke([SystemMessage(content=system), HumanMessage(content=user)]).content
    resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return _content_to_text(resp.content)


def ask_json(llm: Any, system: str, user: str, retries: int = 2) -> dict:
    """Ask for JSON with bounded self-correction when the model returns malformed output."""
    for attempt in range(retries + 1):
        text = ask(llm, system, user)
        try:
            return parse_json(text)
        except LLMError:
            if attempt >= retries or isinstance(llm, MockLLM):
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
    import json
    return json.dumps(payload, ensure_ascii=False)


# ------------------------------------------------------------------ mock brains

def _mock_dispatch(role: str, system: str, user: str) -> str:
    if role == "planner":
        return _mock_planner(user)
    if role == "researcher":
        return _mock_researcher(user)
    if role == "analyst":
        return _mock_analyst(user)
    if role == "writer":
        return _mock_writer(user)
    if role == "critic":
        return _mock_critic(user)
    if role == "classifier":
        from .security.injection import heuristic_scan

        flags = heuristic_scan(user)
        if flags:
            return json.dumps({"is_injection": True, "reason": flags[0]["reason"]})
        return json.dumps({"is_injection": False, "reason": "no pattern matched"})
    return json.dumps({"ok": True})


def _mock_safe_response(role: str, exc: Exception) -> str:
    if role == "planner":
        return json.dumps({"needs_clarification": False, "request_type": "standard", "brief": str(exc)})
    return json.dumps({"ok": False, "error": str(exc)})


def _mock_planner(user: str) -> str:
    try:
        payload = json.loads(user)
        raw = str(payload.get("pm_input", user))
    except Exception:
        raw = user
    text = raw.lower()
    vague_markers = [
        "make it better",
        "make it good",
        "improve things",
        "make it awesome",
        "boost engagement",
        "enhance the app",
        "improve the product",
    ]
    too_short = len(raw.strip()) < 30
    if too_short or any(m in text for m in vague_markers):
        return json.dumps(
            {
                "needs_clarification": True,
                "question": "Which product area should this focus on, and which user segment is affected? "
                "For example: 'activation for new trial signups in our analytics product'.",
            }
        )
    request_type = "standard"
    if any(w in text for w in ("deprecat", "kill", "remove", "sunset")):
        request_type = "deprecation"
    elif any(w in text for w in ("competitor", "competition", "market", "rival")):
        request_type = "competitive"
    return json.dumps(
        {"needs_clarification": False, "request_type": request_type, "brief": raw.strip()[:140]}
    )


def _mock_researcher(user: str) -> str:
    payload = json.loads(user)
    return json.dumps(
        {
            "research_notes": payload.get("notes_summary", []),
            "web_results": payload.get("web_results", []),
            "injection_flags": payload.get("injection_flags", []),
        }
    )


def _mock_analyst(user: str) -> str:
    from .tools.rice import rice_scores

    payload = json.loads(user)
    notes = payload.get("research_notes", [])
    web = payload.get("web_results", [])
    pm_input = payload.get("pm_input", "")

    # corpus-level keyword counting (deterministic "clustering")
    corpus = " ".join(
        " ".join(n.get("signals", []) + n.get("quotes", []) + [n.get("sample", "")]) for n in notes
    ).lower()
    corpus = f"{corpus} {pm_input.lower()}"
    counts = _keyword_counts(corpus)

    themes, contradictions = _cluster_themes(counts)
    total = sum(t["frequency"] for t in themes) or 1
    options = rice_scores(themes, total, pm_input, saturated=_market_saturated(web, pm_input))

    compliance = []
    if any(w in corpus for w in ("gdpr", "eu", "retention", "pii", "privacy")):
        compliance.append("GDPR: data retention & erasure requirements for EU users")
    if any(w in corpus for w in ("deprecat", "kill", "sunset", "remove")):
        compliance.append("Migration path for existing users of the deprecated feature")

    synthesis_md = _mock_synthesis_markdown(pm_input, themes, options, contradictions, compliance)

    return json.dumps(
        {
            "themes": themes,
            "options": options,
            "contradictions": contradictions,
            "memory_hits": payload.get("memory_hits", []),
            "synthesis_markdown": synthesis_md,
            "compliance_dependencies": compliance,
        }
    )


_KEYWORDS = {
    "onboarding": ("onboard", "trial", "signup", "activation", "welcome", "first run"),
    "retention": ("churn", "retention", "cancel", "month 2", "second month", "bounce"),
    "notifications": ("push", "notification", "alert", "digest", "email"),
    "pricing": ("price", "plan", "cost", "tier", "upgrade", "billing"),
    "mobile": ("mobile", "ios", "android", "app"),
    "integrations": ("integrat", "api", "slack", "zapier", "webhook"),
    "performance": ("slow", "latency", "crash", "bug", "error", "loading"),
    "simplicity": ("complex", "confusing", "overwhelm", "steep", "simple"),
    "reporting": ("report", "dashboard", "analytics", "export"),
    "collaboration": ("share", "team", "comment", "permission"),
    "security": ("security", "sso", "gdpr", "compliance", "pii", "privacy"),
}

# words that must match as whole tokens (avoids "app" matching "happy"/"application")
_EXACT_WORDS = {
    "trial", "activation", "welcome", "churn", "retention", "cancel", "bounce",
    "push", "notification", "alert", "digest", "email",
    "price", "plan", "cost", "tier", "upgrade", "billing",
    "mobile", "ios", "android", "app",
    "api", "slack", "zapier", "webhook",
    "slow", "latency", "crash", "bug", "error", "loading",
    "complex", "confusing", "steep", "simple",
    "dashboard", "analytics", "export",
    "share", "team", "comment", "permission",
    "security", "sso", "gdpr", "compliance", "pii", "privacy",
}


def _kw_re(kw: str) -> str:
    if kw in _EXACT_WORDS:
        return r"(?<!\w)" + re.escape(kw) + r"\b"
    return r"(?<!\w)" + re.escape(kw) + r"\w*"


def _keyword_counts(corpus: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for theme, kws in _KEYWORDS.items():
        total = 0
        for kw in kws:
            total += len(re.findall(_kw_re(kw), corpus))
        if total:
            counts[theme] = total
    return counts


def _cluster_themes(counts: dict[str, int]) -> tuple[list[dict], list[dict]]:
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[: config.TOP_THEMES]
    themes = []
    for theme, freq in ordered:
        sentiment = "mixed"
        if theme in ("performance", "simplicity"):
            sentiment = "negative"
        if theme in ("notifications", "integrations"):
            sentiment = "positive"
        themes.append(
            {
                "name": theme,
                "frequency": freq,
                "sentiment": sentiment,
                "representative_quote": f"Representative quote for {theme} (mock)",
                "sources": ["tickets", "reviews"],
            }
        )
    contradictions = []
    if "simplicity" in counts:
        contradictions.append(
            {
                "name": "complexity split",
                "detail": f"{counts.get('simplicity', 0)} mentions call the product too complex while "
                "interviews describe it as too simple — opposing segment experiences",
            }
        )
    return themes, contradictions


def _market_saturated(web: list[dict], pm_input: str) -> bool:
    text = pm_input.lower()
    if not any(w in text for w in ("competitor", "market", "rival", "competition")):
        return False
    n_competitors = sum(1 for r in web if "competitor" in r.get("title", "").lower())
    return n_competitors >= 3


def _mock_synthesis_markdown(pm_input, themes, options, contradictions, compliance) -> str:
    lines = [f"# Research Synthesis — {pm_input[:80]}", ""]
    lines.append("## Themes (clustered from sources)")
    for t in themes:
        lines.append(
            f"- **{t['name']}** ({t['sentiment']}) — {t['frequency']} mentions. "
            f"Quote: \"{t['representative_quote']}\""
        )
    lines.append("")
    if contradictions:
        lines.append("## Contradictions (named risks)")
        for c in contradictions:
            lines.append(f"- ⚠ {c['name']}: {c['detail']}")
        lines.append("")
    lines.append("## Sourced RICE options")
    for o in options:
        lines.append(
            f"- **{o['name']}** — RICE {o['rice']:.2f} (Reach {o['reach']}, Impact {o['impact']}, "
            f"Confidence {o['confidence']} [{o['confidence_label']}], Effort {o['effort']})"
        )
    if compliance:
        lines.append("")
        lines.append("## Compliance dependencies")
        for c in compliance:
            lines.append(f"- {c}")
    return "\n".join(lines)


def _mock_writer(user: str) -> str:
    payload = json.loads(user)
    synthesis = payload.get("synthesis", "")
    options = payload.get("options", [])
    pm_input = payload.get("pm_input", "")
    contradictions = payload.get("contradictions", [])
    compliance = payload.get("compliance_dependencies", [])
    deprecation = payload.get("request_type") == "deprecation" or "deprecat" in pm_input.lower()
    feedback = payload.get("pm_prd_feedback") or payload.get("critic_feedback") or []
    seed = "\n".join(f"> {f}" for f in feedback[:3]) if feedback else ""

    parts = [
        f"# PRD — {_title_from(pm_input)}",
        f"> PM input: {pm_input}",
        "",
        f"## 1. Problem Statement",
        f"Evidence from {len(synthesis.split(chr(10)))} synthesis rows (mock draft). "
        f"Quotes and counts are carried from the approved synthesis.",
        seed,
        "",
        "## 2. User Segment",
        "Affected segment derived from source volume (tickets + reviews + NPS) — "
        "see synthesis for per-theme counts.",
        "",
        "## 3. Success Metrics",
        "Primary: activation rate at month 2 improves by ≥10% relative to baseline (funnel step: trial → active).",
        "",
        "## 4. Opportunity Sizing",
        *([f"- **{o['name']}** — RICE {o['rice']:.2f} (Confidence {o['confidence_label']})" for o in options] or ["- n/a"]),
        "",
        "## 5. Proposed Solution",
        f"Scope the lead option: {options[0]['name'] if options else 'to be confirmed'}.",
        "",
        "## 6. Risks & Mitigations",
        *([f"- Risk: {c['name']} — mitigation: address segments separately, A/B split" for c in contradictions] or ["- None material identified"]),
        *(["⚠ Compliance: " + c for c in compliance]),
        "",
        "## 7. Dependencies",
        *(["- " + c for c in compliance] or ["- Engineering: feature-flagged rollout"]),
        "",
        "## 8. Assumptions",
        "- Activation metric is instrumented (verifiable in 1 sprint).",
        "- Segment definition holds; invalidated if funnel data shows otherwise.",
        "",
    ]
    if deprecation:
        parts += [
            "## 9. Migration / Deprecation Path",
            "Grace window of 2 quarters, export tooling for affected customers, in-app migration notice.",
        ]
    if feedback:
        parts += ["", "## 10. Revision — addressing feedback"]
        for f in feedback[:6]:
            dim = f.split(":")[0].strip()
            parts.append(f"- {dim}: addressed — evidence added to the relevant section above.")
    return "\n".join(parts)


def _title_from(pm_input: str) -> str:
    title = re.sub(r"\s+", " ", pm_input.strip())
    return title[:70] + ("…" if len(title) > 70 else "")


def _mock_critic(user: str) -> str:
    draft = json.loads(user).get("prd_draft", "")
    low = draft.lower()
    # strip negated statements so "no risks" does not satisfy the "risk" check
    positive = low
    for neg in (
        "no risk", "no risks", "no rice", "no evidence", "no metric", "no metrics",
        "no dependency", "no dependencies", "no assumption", "no assumptions",
        "no segment", "no user segment", "none", "not included", "missing",
    ):
        positive = positive.replace(neg, "")
    scores = {}
    feedback = []

    def has(*needles: str) -> bool:
        return any(n in positive for n in needles)

    scores["problem_clarity"] = 8 if has("problem statement", "evidence", "quote") else 3
    scores["user_segment"] = 8 if has("segment", "volume") else 3
    scores["measurable_metric"] = 8 if has("activation", "%", "metric", "retention") else 3
    scores["opportunity_size"] = 8 if has("rice", "confidence") else 3
    scores["risk_articulation"] = 8 if has("risk", "mitigation") else 3
    scores["dependencies"] = 8 if has("dependencies", "gdpr", "retention", "engineering") else 3
    scores["assumptions"] = 8 if has("assumptions", "invalidated", "testable") else 3

    for dim, score in scores.items():
        if score < 7:
            feedback.append(f"{dim}: below bar ({score}/10) — make it specific and evidenced")

    if "tbd" in low or "placeholder" in low:
        feedback.append("draft contains placeholder text")
    if "## 9" not in low and has("deprecat"):
        feedback.append("deprecation decision requires a migration path section")
    if has("gdpr") and not has("retention"):
        feedback.append("GDPR-constrained feature missing data retention requirement")

    # genuine improvement: a revision section that explicitly addresses a flagged
    # dimension lifts that dimension's score
    revision_section = low.split("## 10. revision")[1] if "## 10. revision" in low else ""
    for dim, score in list(scores.items()):
        if score < 7 and dim != "overall" and dim in revision_section and "addressed" in revision_section:
            scores[dim] = 9

    overall = round(sum(scores.values()) / len(scores), 2)
    scores["overall"] = overall
    return json.dumps(
        {
            "scores": scores,
            "overall": overall,
            "feedback": feedback,
            "critical_issues": [f for f in feedback if "gdpr" in f or "migration" in f],
        }
    )

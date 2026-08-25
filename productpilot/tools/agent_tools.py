"""LangChain tools for agent function-calling."""
from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from .ingestion import load_sources, SourceChunk
from .search import web_search
from .rice import rice_scores
from ..memory.stores import vector_store
from ..security.injection import heuristic_scan, sanitize_text


@tool
def ingest_sources(paths: list[str], pm_input: str) -> dict:
    """Ingest raw source files (CSV, JSON, MD), sanitize, and return structured notes + digest.

    Returns: {
        "notes_summary": [{"source", "kind", "volume", "signals", "quotes", "sample"}],
        "digest": "bounded text digest for LLM context",
        "web_results": "external market research from Tavily",
        "injection_flags": [{"source", "snippet", "reason"}],
        "missing_files": [...]
    }
    """
    from collections import defaultdict

    SAMPLE_ROWS = 200
    DIGEST_ROWS_PER_KIND = 60
    DIGEST_MAX_CHARS = 15_000

    _SIGNAL_MAP = {
        "ticket": ("confusing", "slow", "missing", "error", "hard"),
        "review": ("rating", "praise", "complaint", "mobile", "price"),
        "nps": ("detractor", "promoter", "passive", "comment"),
        "interview": ("interview", "said", "wants", "struggles", "uses"),
    }

    def _signals(kind: str, pm_input: str, group: list) -> list[str]:
        joined = " ".join(c.text.lower() for c in group)
        words = _SIGNAL_MAP.get(kind, ("feedback",))
        hits = [w for w in words if w in joined]
        signals = [f"{kind}-signal: '{w}' appears in {joined.count(w)} documents" for w in hits[:4]]
        if pm_input:
            signals.append(f"relates to PM focus: {pm_input[:80]}")
        return signals or [f"parsed {len(group)} {kind} records"]

    chunks = load_sources(paths)

    per_chunk_flags = {i: heuristic_scan(c.text) for i, c in enumerate(chunks)}
    flags: list[dict] = []
    for i, c in enumerate(chunks):
        for f in per_chunk_flags[i]:
            f = dict(f)
            f["source"] = c.source_path
            flags.append(f)
    if flags:
        try:
            from .. import llm, prompts
            classifier = llm.get_llm("classifier")
            verdict = llm.ask_json(classifier, prompts.CLASSIFIER, " ".join(f["snippet"] for f in flags))
            if not verdict.get("is_injection", True):
                flags = []
        except Exception:
            pass

    sanitized = [
        sanitize_text(c.text, per_chunk_flags[i]) if per_chunk_flags[i] else c.text
        for i, c in enumerate(chunks)
    ]

    by_kind: dict[str, list] = defaultdict(list)
    for c, text in zip(chunks, sanitized):
        by_kind[c.kind].append((c, text))

    notes_summary = []
    for kind, group in sorted(by_kind.items()):
        volume = len(group)
        texts = [t for _, t in group]
        quotes = [t[:160].replace("\n", " ") for t in texts[:3]]
        sample = " ".join(texts[:SAMPLE_ROWS])
        signals = _signals(kind, pm_input, [c for c, _ in group])
        notes_summary.append(
            {
                "source": group[0][0].source_path,
                "kind": kind,
                "volume": volume,
                "signals": signals[:5],
                "quotes": quotes,
                "sample": sample,
            }
        )

    digest_parts = []
    used = 0
    for kind, group in sorted(by_kind.items()):
        for _, text in group[:DIGEST_ROWS_PER_KIND]:
            piece = text[:300].replace("\n", " ")
            if used + len(piece) > DIGEST_MAX_CHARS:
                break
            digest_parts.append(f"[{kind}] {piece}")
            used += len(piece)
        if used >= DIGEST_MAX_CHARS:
            break
    digest = "\n".join(digest_parts)

    web = web_search(f"{pm_input} competitors 2026")

    return {
        "notes_summary": notes_summary,
        "digest": digest,
        "web_results": web,
        "injection_flags": flags,
        "missing_files": [c.source_path for c in chunks if c.kind == "error"],
    }


@tool
def search_web(query: str) -> str:
    """Search the web for competitive/market context via Tavily."""
    return web_search(query)


@tool
def search_memory(query: str, k: int = 5) -> list[dict]:
    """Search org memory (vector store) for relevant past PRDs/research."""
    try:
        hits = vector_store().search(query, k=k)
        return [
            {
                "title": h["title"],
                "doc_type": h["doc_type"],
                "source": h["source"],
                "score": h["score"],
                "snippet": h["text"][:400],
            }
            for h in hits
        ]
    except Exception:
        return []


@tool
def calculate_rice(
    themes: list[dict],
    total_volume: int,
    pm_input: str,
    saturated: bool = False,
    deprecation: bool = False,
) -> list[dict]:
    """Calculate sourced RICE scores for theme clusters. Deterministic given themes."""
    return rice_scores(themes, total_volume, pm_input, saturated, deprecation)


RESEARCHER_TOOLS = [ingest_sources, search_web]
ANALYST_TOOLS = [search_memory, calculate_rice]
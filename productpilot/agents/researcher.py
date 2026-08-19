"""Researcher — ingests raw sources, gathers web context, flags prompt injection.

Ingestion, injection scanning, and web search run in the agent itself (both mock and
real modes). The model receives a bounded, *sanitized* digest of the sources plus a
structured per-source summary — never raw, unsanitized file content.
"""
from __future__ import annotations

from collections import defaultdict

from .. import config, llm, prompts
from ..security.injection import heuristic_scan, sanitize_text
from ..tools.ingestion import load_sources
from ..tools.search import web_search
from .planner import llm_json_payload

_SIGNAL_MAP = {
    "ticket": ("confusing", "slow", "missing", "error", "hard"),
    "review": ("rating", "praise", "complaint", "mobile", "price"),
    "nps": ("detractor", "promoter", "passive", "comment"),
    "interview": ("interview", "said", "wants", "struggles", "uses"),
}

SAMPLE_ROWS = 200
DIGEST_ROWS_PER_KIND = 60
DIGEST_MAX_CHARS = 15_000


def _signals(kind: str, pm_input: str, group: list) -> list[str]:
    joined = " ".join(c.text.lower() for c in group)
    words = _SIGNAL_MAP.get(kind, ("feedback",))
    hits = [w for w in words if w in joined]
    signals = [f"{kind}-signal: '{w}' appears in {joined.count(w)} documents" for w in hits[:4]]
    if pm_input:
        signals.append(f"relates to PM focus: {pm_input[:80]}")
    return signals or [f"parsed {len(group)} {kind} records"]


def ingest(paths: list[str], pm_input: str) -> dict:
    """Parse sources, scan + sanitize content, run web research. Shared by mock & real."""
    chunks = load_sources(paths)

    per_chunk_flags = {i: heuristic_scan(c.text) for i, c in enumerate(chunks)}
    flags: list[dict] = []
    for i, c in enumerate(chunks):
        for f in per_chunk_flags[i]:
            f = dict(f)
            f["source"] = c.source_path
            flags.append(f)
    if flags and not config.MOCK:
        try:
            classifier = llm.get_llm("classifier")
            verdict = llm.ask_json(
                classifier,
                prompts.CLASSIFIER,
                " ".join(f["snippet"] for f in flags),
            )
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


def run(state: dict) -> dict:
    model = llm.get_llm("researcher")
    paths = state.get("source_paths", [])
    pm_input = state.get("pm_input", "")

    research = ingest(paths, pm_input)

    payload = {
        "source_paths": paths,
        "pm_input": pm_input,
        "org_name": state.get("org_name", ""),
        "request_type": state.get("request_type", "standard"),
        "notes_summary": research["notes_summary"],
        "digest": research["digest"],
        "web_results": research["web_results"],
        "injection_flags": research["injection_flags"],
        "missing_files": research["missing_files"],
    }
    response = llm.ask_json(model, prompts.RESEARCHER, llm_json_payload(payload))
    parsed = response

    research_notes = parsed.get("research_notes") or research["notes_summary"]
    return {
        "research_notes": research_notes,
        "web_results": research["web_results"],
        "injection_flags": research["injection_flags"],
        "status": "research_done",
    }
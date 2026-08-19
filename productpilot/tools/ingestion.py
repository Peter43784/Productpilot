"""Raw source ingestion: CSV (Zendesk/G2/NPS), JSON/JSONL, Markdown, TXT.

Every chunk remembers its provenance so the trace can point back to a source.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class SourceChunk:
    source_path: str
    kind: str  # ticket | review | nps | interview | notes | doc
    text: str
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"source_path": self.source_path, "kind": self.kind, "text": self.text, "meta": self.meta}


_SUPPORTED = {".csv", ".tsv", ".json", ".jsonl", ".md", ".txt", ".markdown"}


def load_sources(paths: list[str]) -> list[SourceChunk]:
    """Parse every provided file into SourceChunks (never raises; bad files are noted as chunks)."""
    chunks: list[SourceChunk] = []
    for raw in paths or []:
        p = Path(raw)
        if not p.exists():
            chunks.append(SourceChunk(str(p), "error", f"[missing file: {raw}]", {"error": "not found"}))
            continue
        try:
            if p.suffix.lower() in (".csv", ".tsv"):
                chunks.extend(_load_tabular(p))
            elif p.suffix.lower() in (".json", ".jsonl"):
                chunks.extend(_load_json(p))
            elif p.suffix.lower() in (".md", ".txt", ".markdown"):
                chunks.append(SourceChunk(str(p), _kind_of(p), p.read_text(encoding="utf-8", errors="replace")))
            else:
                chunks.append(SourceChunk(str(p), "doc", p.read_text(encoding="utf-8", errors="replace")))
        except Exception as exc:  # keep the graph alive; note the failure in the trace
            chunks.append(SourceChunk(str(p), "error", f"[failed to parse: {exc}]", {"error": str(exc)}))
    return chunks


def _kind_of(p: Path) -> str:
    name = p.name.lower()
    if "ticket" in name or "zendesk" in name:
        return "ticket"
    if "review" in name or "g2" in name:
        return "review"
    if "nps" in name or "survey" in name:
        return "nps"
    if "interview" in name or "transcript" in name:
        return "interview"
    if "competitor" in name or "research" in name or "scan" in name:
        return "notes"
    return "doc"


def _row_to_text(row: dict, cols: dict) -> str:
    parts = []
    for key, label in cols.items():
        val = row.get(key)
        if val is not None and str(val).strip() and str(val).lower() not in ("nan", "none", "null"):
            parts.append(f"{label}: {str(val).strip()}")
    return " | ".join(parts) if parts else " "


def _load_tabular(p: Path) -> list[SourceChunk]:
    sep = "\t" if p.suffix.lower() == ".tsv" else ","
    df = pd.read_csv(p, sep=sep, dtype=str, on_bad_lines="skip")
    df = df.fillna("")
    cols = {c: c for c in df.columns}
    # map common column names to readable labels
    aliases = {
        "subject": "subject", "description": "description", "body": "description",
        "title": "title", "review": "body", "review_text": "body",
        "score": "NPS score", "rating": "rating", "comment": "comment", "feedback": "comment",
    }
    labeled = {}
    for c in df.columns:
        labeled[c] = aliases.get(c.strip().lower(), c)
    kind = _kind_of(p)
    rows = []
    for _, row in df.iterrows():
        text = _row_to_text(row, labeled)
        if text.strip(" |"):
            rows.append(
                SourceChunk(
                    str(p),
                    kind,
                    text,
                    {"row": int(row.name), "columns": list(df.columns)},
                )
            )
    return rows


def _load_json(p: Path) -> list[SourceChunk]:
    kind = _kind_of(p)
    data = p.read_text(encoding="utf-8")
    records = []
    if p.suffix.lower() == ".jsonl":
        records = [json.loads(line) for line in data.splitlines() if line.strip()]
    else:
        parsed = json.loads(data)
        records = parsed if isinstance(parsed, list) else [parsed]
    chunks = []
    for i, rec in enumerate(records):
        if isinstance(rec, str):
            text = rec
        elif isinstance(rec, dict):
            text = _row_to_text(rec, {c: c for c in rec})
        else:
            text = str(rec)
        if text.strip(" |"):
            chunks.append(SourceChunk(str(p), kind, text, {"row": i}))
    return chunks

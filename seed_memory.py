"""Seed org memory (SQLite + vector index) from historical research and PRDs.

Run once (idempotent) before demos so the Analyst can recall prior decisions:
python seed_memory.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from productpilot import config
from productpilot.memory.stores import sqlite_store, vector_store


def seed() -> dict:
    store = sqlite_store()
    vec = vector_store()
    seeded = {"docs": 0, "prds": 0, "skipped": 0}

    for md_file in sorted(config.SEED_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        existing = [h for h in vec.search(md_file.stem, k=3, doc_type="research")
                    if h.get("source") == f"seed://{md_file.name}"]
        if existing:
            seeded["skipped"] += 1
            continue
        vec.index(text, "research", md_file.stem, source=f"seed://{md_file.name}")
        seeded["docs"] += 1

    return seeded


def main() -> int:
    result = seed()
    print(f"Seeded {result['docs']} new memory doc(s), {result['skipped']} already present.")
    print(f"Vector index: {vector_store().count()} docs · backend={vector_store().backend}")
    print(f"SQLite: {len(sqlite_store().list_prds(1000))} PRDs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
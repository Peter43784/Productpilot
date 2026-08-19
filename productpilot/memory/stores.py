"""Lazy singletons for the memory layer (shared by graph, API, UI)."""
from __future__ import annotations

from .sqlite_store import SQLiteStore
from .vector_store import VectorStore

_store: SQLiteStore | None = None
_vector: VectorStore | None = None


def sqlite_store() -> SQLiteStore:
    global _store
    if _store is None:
        _store = SQLiteStore()
    return _store


def vector_store() -> VectorStore:
    global _vector
    if _vector is None:
        _vector = VectorStore()
    return _vector

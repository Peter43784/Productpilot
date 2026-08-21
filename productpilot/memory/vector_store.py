"""Semantic org memory.

Primary backend is Chroma (persistent, in-process). If Chroma is unavailable on the
platform (e.g. very new Python versions), we transparently fall back to a numpy-based
index with the same interface — the "0 infrastructure" story stays intact.

Embeddings: pluggable via PP_EMBEDDING_BACKEND (auto|gemini|local|hash). 
- `local`: Sentence Transformers (free, offline, no API key needed)
- `gemini`: Google Gemini API (requires GEMINI_API_KEY from Google Cloud)
- `hash`: Deterministic hash-based embeddings (fastest, no dependencies)
- `auto`: Uses local if available, then Gemini if key set, otherwise hash
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.request
from pathlib import Path

import numpy as np

from .. import config

log = logging.getLogger("productpilot.vector_store")

EMBED_DIM = 256

_EMBED_PRESETS: dict[str, dict] = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/",
        "key": "GEMINI_API_KEY",
        "model": "models/text-embedding-004",
    },
}


def _hash_embed(text: str) -> list[float]:
    vec = np.zeros(EMBED_DIM, dtype=np.float64)
    for token in text.lower().split():
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16)
        vec[h % EMBED_DIM] += 1.0
    norm = np.linalg.norm(vec)
    if norm:
        vec /= norm
    return vec.tolist()


def _local_embed(texts: list[str]) -> list[list[float]]:
    """Sentence Transformers embeddings (free, offline, no API key needed)."""
    try:
        # Suppress optional dependency warnings from transformers
        import warnings
        warnings.filterwarnings("ignore", category=UserWarning)
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = model.encode(texts, convert_to_tensor=False)
        return embeddings.tolist() if hasattr(embeddings, 'tolist') else [e.tolist() if hasattr(e, 'tolist') else list(e) for e in embeddings]
    except ImportError as e:
        if "torchvision" in str(e) or "torch" in str(e):
            log.warning("sentence-transformers optional dependencies missing — falling back to hash embeddings. Install with: pip install -r requirements.txt")
        else:
            log.warning("sentence-transformers not installed — falling back to hash embeddings. Install with: pip install -r requirements.txt")
        return [_hash_embed(t) for t in texts]
    except Exception as e:
        log.warning("local embedding failed (%s) — falling back to hash embeddings", e)
        return [_hash_embed(t) for t in texts]


def _remote_embed(texts: list[str], base_url: str, api_key: str, model: str) -> list[list[float]]:
    """Gemini embeddings via Google AI Studio API (stdlib only)."""
    embeddings = []
    for text in texts:
        payload = {
            "model": model,
            "content": {"parts": [{"text": text}]}
        }
        # Google AI Studio endpoint requires API key in query string
        url = f"{base_url.rstrip('/')}/{model}:embedContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            embeddings.append(body["embedding"]["values"])
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            log.debug(f"Gemini API error - Status {e.code}: {error_body[:500]}")
            log.debug(f"URL: {url[:150]}")
            raise
        except Exception as e:
            log.debug(f"Gemini embedding failed for URL: {url[:100]}... Error: {e}")
            raise
    return embeddings


def _active_backend() -> str:
    if config.EMBEDDING_BACKEND != "auto":
        return config.EMBEDDING_BACKEND
    if config.MOCK:
        return "hash"
    # Try local > gemini > hash
    try:
        import sentence_transformers
        return "local"
    except ImportError:
        pass
    except Exception as exc:
        # Some transformer optional dependency failures bubble up as runtime
        # exceptions, not ImportError (e.g. mismatched torchvision/torch stack).
        log.warning("local embedding backend unavailable (%s)", exc)
    return "gemini" if os.getenv(_EMBED_PRESETS["gemini"]["key"]) else "hash"


def embed(texts: list[str]) -> list[list[float]]:
    backend = _active_backend()
    if backend == "hash":
        return [_hash_embed(t) for t in texts]
    if backend == "local":
        return _local_embed(texts)
    preset = _EMBED_PRESETS.get(backend)
    if preset is None:
        log.warning("unknown embedding backend %r — falling back to hash embeddings", backend)
        return [_hash_embed(t) for t in texts]
    try:
        return _remote_embed(texts, preset["base_url"], os.getenv(preset["key"]) or "", preset["model"])
    except Exception as exc:
        log.warning("embedding backend %s failed (%s) — falling back to hash embeddings", backend, exc)
        return [_hash_embed(t) for t in texts]


class MemoryDoc:
    def __init__(
        self,
        text: str,
        doc_type: str,
        title: str,
        source: str = "",
        meta: dict | None = None,
        embedding: list[float] | None = None,
    ):
        self.text = text
        self.doc_type = doc_type  # prd | synthesis | research
        self.title = title
        self.source = source
        self.meta = meta or {}
        self.embedding = embedding if embedding is not None else embed([text])[0]

    def to_dict(self) -> dict:
        return {
            "text": self.text, "doc_type": self.doc_type, "title": self.title,
            "source": self.source, "meta": self.meta, "embedding": self.embedding,
        }


class VectorStore:
    """Semantic memory over past PRDs, syntheses, and research."""

    def __init__(self, backend: str | None = None):
        self._docs: list[MemoryDoc] = []
        if backend is None:
            backend = "chroma" if _chroma_available() else "numpy"
        self.backend = backend
        if backend == "chroma":
            self._collection = _init_chroma()
        else:
            self._collection = None
        self._load_local()

    # -- public API -----------------------------------------------------------

    def index(self, text: str, doc_type: str, title: str, source: str = "", meta: dict | None = None) -> None:
        doc = MemoryDoc(text, doc_type, title, source, meta)
        self._docs.append(doc)
        if self.backend == "chroma" and self._collection is not None:
            try:
                self._collection.add(
                    ids=[f"{doc_type}-{len(self._docs)}"],
                    embeddings=[doc.embedding],
                    documents=[doc.text],
                    metadatas=[{"doc_type": doc_type, "title": title, "source": source}],
                )
            except Exception:
                pass
        _persist_doc(doc)

    def search(self, query: str, k: int = 5, doc_type: str | None = None) -> list[dict]:
        if self.backend == "chroma" and self._collection is not None:
            try:
                results = self._collection.query(
                    query_embeddings=[embed([query])[0]],
                    n_results=k,
                    where={"doc_type": doc_type} if doc_type else None,
                )
                return [
                    {
                        "text": d, "title": m.get("title", ""), "doc_type": m.get("doc_type", ""),
                        "source": m.get("source", ""), "score": s,
                    }
                    for d, m, s in zip(
                        results.get("documents", [[]])[0],
                        results.get("metadatas", [[]])[0],
                        results.get("distances", [[]])[0],
                    )
                ]
            except Exception:
                pass
        qv = np.array(embed([query])[0])
        scored = []
        for doc in self._docs:
            if doc_type and doc.doc_type != doc_type:
                continue
            dv = np.array(doc.embedding)
            if dv.shape[0] != qv.shape[0]:
                continue  # doc embedded with a different backend — re-seed to migrate
            score = float(np.dot(qv, dv) / max(np.linalg.norm(qv) * np.linalg.norm(dv), 1e-9))
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"text": d.text, "title": d.title, "doc_type": d.doc_type, "source": d.source, "score": round(s, 4)}
            for s, d in scored[:k]
        ]

    def count(self) -> int:
        return len(self._docs)

    # -- persistence ------------------------------------------------------------

    def _load_local(self) -> None:
        blob = _local_blob_path()
        if blob.exists():
            try:
                for rec in json.loads(blob.read_text(encoding="utf-8")):
                    self._docs.append(
                        MemoryDoc(
                            rec["text"], rec["doc_type"], rec["title"],
                            rec.get("source", ""), rec.get("meta", {}),
                            embedding=rec.get("embedding"),
                        )
                    )
            except Exception:
                self._docs = []


def _local_blob_path() -> Path:
    return config.DB_DIR / "memory_blob.json"


def _persist_doc(doc: MemoryDoc) -> None:
    blob = _local_blob_path()
    records = []
    if blob.exists():
        try:
            records = json.loads(blob.read_text(encoding="utf-8"))
        except Exception:
            records = []
    records.append(doc.to_dict())
    blob.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")


def _chroma_available() -> bool:
    try:
        import chromadb  # noqa: F401

        return True
    except Exception:
        return False


def _init_chroma():
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        return client.get_or_create_collection(
            "productpilot_memory", metadata={"hnsw:space": "cosine"}
        )
    except Exception:
        return None

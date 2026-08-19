"""SQLite structured memory: PRDs, decisions, trace bundles.

This is the 'org memory' for structured facts — decisions, dates, RICE values,
approval status. Semantic search lives in the vector store.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from .. import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    pm_input TEXT,
    org_name TEXT,
    prd_markdown TEXT,
    critic_scores_json TEXT,
    overall_critic REAL,
    status TEXT,
    trace_json TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prd_id INTEGER,
    option_name TEXT,
    rice REAL,
    confidence_label TEXT,
    rationale TEXT
);
CREATE INDEX IF NOT EXISTS idx_decisions_prd ON decisions(prd_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteStore:
    def __init__(self, path=None):
        self.path = str(path or config.SQLITE_PATH)
        conn = sqlite3.connect(self.path)
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def save_prd(
        self,
        title: str,
        pm_input: str,
        prd_markdown: str,
        critic_scores: dict,
        status: str,
        trace: dict,
        org_name: str = "",
        decisions: list[dict] | None = None,
    ) -> int:
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO prds (title, pm_input, org_name, prd_markdown, critic_scores_json,"
                " overall_critic, status, trace_json, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    title,
                    pm_input,
                    org_name,
                    prd_markdown,
                    json.dumps(critic_scores),
                    critic_scores.get("overall"),
                    status,
                    json.dumps(trace, default=str),
                    _now(),
                ),
            )
            prd_id = int(cur.lastrowid)
            for d in decisions or []:
                conn.execute(
                    "INSERT INTO decisions (prd_id, option_name, rice, confidence_label, rationale)"
                    " VALUES (?,?,?,?,?)",
                    (prd_id, d.get("name"), d.get("rice"), d.get("confidence_label"), d.get("rationale")),
                )
            conn.commit()
            return prd_id
        finally:
            conn.close()

    def list_prds(self, limit: int = 20) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, title, pm_input, org_name, overall_critic, status, created_at"
                " FROM prds ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                {
                    "id": r[0], "title": r[1], "pm_input": r[2], "org_name": r[3],
                    "critic_overall": r[4], "status": r[5], "created_at": r[6],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_prd(self, prd_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM prds WHERE id = ?", (prd_id,)
            ).fetchone()
            if not row:
                return None
            keys = [d[0] for d in conn.execute("SELECT * FROM prds LIMIT 0").description]
            record = dict(zip(keys, row))
            for k in ("critic_scores_json", "trace_json"):
                try:
                    record[k.replace("_json", "")] = json.loads(record[k])
                except Exception:
                    record[k.replace("_json", "")] = {}
            return record
        finally:
            conn.close()

    def search_decisions(self, term: str, limit: int = 10) -> list[dict]:
        conn = self._conn()
        try:
            like = f"%{term}%"
            rows = conn.execute(
                "SELECT d.option_name, d.rice, d.confidence_label, d.rationale, p.title, p.created_at"
                " FROM decisions d JOIN prds p ON p.id = d.prd_id"
                " WHERE d.option_name LIKE ? OR d.rationale LIKE ? OR p.title LIKE ?"
                " ORDER BY p.id DESC LIMIT ?",
                (like, like, like, limit),
            ).fetchall()
            return [
                {
                    "option": r[0], "rice": r[1], "confidence": r[2], "rationale": r[3],
                    "prd_title": r[4], "created_at": r[5],
                }
                for r in rows
            ]
        finally:
            conn.close()

"""Evidence store: every automated result must be verifiable."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DB = Path(os.getenv("EVIDENCE_DB", "db/evidence.sqlite3"))


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute(
        """CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created TEXT DEFAULT CURRENT_TIMESTAMP,
            kind TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            source TEXT,
            payload TEXT,
            verdict TEXT NOT NULL
        )"""
    )
    c.commit()
    return c


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def add(kind: str, data: bytes, payload: dict[str, Any], verdict: str, source: str = "") -> int:
    """Store evidence. `verdict` is 'verified' or 'unverified' (fail closed)."""
    c = _conn()
    cur = c.execute(
        "INSERT INTO evidence(kind, sha256, source, payload, verdict) VALUES (?,?,?,?,?)",
        (kind, sha256_bytes(data), source, json.dumps(payload, ensure_ascii=False), verdict),
    )
    c.commit()
    return int(cur.lastrowid)


def get(item_id: int) -> dict[str, Any] | None:
    c = _conn()
    row = c.execute(
        "SELECT id, created, kind, sha256, source, payload, verdict FROM evidence WHERE id=?",
        (item_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "created": row[1],
        "kind": row[2],
        "sha256": row[3],
        "source": row[4],
        "payload": json.loads(row[5]),
        "verdict": row[6],
    }

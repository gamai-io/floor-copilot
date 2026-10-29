"""Evidence store: every automated result must be verifiable."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
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
            verdict TEXT NOT NULL,
            token TEXT
        )"""
    )
    cols = {row[1] for row in c.execute("PRAGMA table_info(evidence)")}
    if "token" not in cols:
        c.execute("ALTER TABLE evidence ADD COLUMN token TEXT")
    c.commit()
    return c


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def add(kind: str, data: bytes, payload: dict[str, Any], verdict: str,
        source: str = "") -> dict[str, Any]:
    """Store evidence and return a public id plus an unguessable access token.

    `verdict` is 'verified' or 'unverified' (fail closed). The token prevents
    enumeration of other users' uploads through /api/evidence/{id}.
    """
    token = secrets.token_urlsafe(12)
    c = _conn()
    cur = c.execute(
        "INSERT INTO evidence(kind, sha256, source, payload, verdict, token) VALUES (?,?,?,?,?,?)",
        (kind, sha256_bytes(data), source, json.dumps(payload, ensure_ascii=False), verdict, token),
    )
    c.commit()
    return {"id": int(cur.lastrowid), "token": token}


def get(item_id: int, token: str = "") -> dict[str, Any] | None:
    c = _conn()
    row = c.execute(
        "SELECT id, created, kind, sha256, source, payload, verdict, token FROM evidence WHERE id=?",
        (item_id,),
    ).fetchone()
    if not row or not row[7] or not secrets.compare_digest(str(row[7]), str(token)):
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

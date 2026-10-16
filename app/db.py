"""SQLite persistence for uploaded documents and their summaries."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT    NOT NULL,
    file_type   TEXT    NOT NULL,
    size_bytes  INTEGER NOT NULL,
    word_count  INTEGER NOT NULL,
    text        TEXT    NOT NULL,
    uploaded_at TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS summaries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id),
    abstractive  TEXT    NOT NULL,
    extractive   TEXT    NOT NULL,
    quality_json TEXT    NOT NULL,
    model        TEXT    NOT NULL,
    created_at   TEXT    NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)


def save_document(filename: str, file_type: str, size_bytes: int, word_count: int, text: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO documents (filename, file_type, size_bytes, word_count, text, uploaded_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (filename, file_type, size_bytes, word_count, text, _now()),
        )
        return cur.lastrowid


def get_document(document_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()


def save_summary(document_id: int, abstractive: str, extractive: str, quality: dict, model: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO summaries (document_id, abstractive, extractive, quality_json, model, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (document_id, abstractive, extractive, json.dumps(quality), model, _now()),
        )
        return cur.lastrowid

# -*- coding: utf-8 -*-
"""
db.py
======
Minimal SQLite-backed job store. No ORM -- the schema is small and
stable enough that raw SQL is clearer than adding a dependency.

Job lifecycle (status column):
    uploaded            -> file received, price shown, awaiting payment
    payment_pending      -> redirected to ZarinPal, waiting for callback
    paid                 -> payment verified, queued for conversion
    converting            -> worker is running Converter on this job
    done                  -> output file ready for download
    failed                -> conversion raised an error (see error_message)
    payment_failed         -> ZarinPal verification failed/cancelled

A job's output is only ever served after status == 'done' AND the
caller supplies the job's download_token (random, unguessable) -- see
routes/download.py.
"""
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager

from . import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    created_at       REAL NOT NULL,
    status            TEXT NOT NULL,
    upload_path        TEXT,
    output_path         TEXT,
    original_filename    TEXT,
    price_rials           INTEGER NOT NULL,
    zarinpal_authority     TEXT,
    zarinpal_ref_id         TEXT,
    download_token            TEXT,
    error_message              TEXT,
    record_count                 INTEGER,
    updated_at                    REAL NOT NULL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(str(settings.DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(SCHEMA)


def create_job(job_id: str, upload_path: str, original_filename: str, price_rials: int) -> None:
    now = time.time()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO jobs (id, created_at, status, upload_path, original_filename,
                                  price_rials, updated_at)
               VALUES (?, ?, 'uploaded', ?, ?, ?, ?)""",
            (job_id, now, upload_path, original_filename, price_rials, now),
        )


def get_job(job_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def update_job(job_id: str, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [job_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE jobs SET {cols} WHERE id = ?", values)


def generate_download_token() -> str:
    return secrets.token_urlsafe(32)


def list_stale_jobs(older_than_seconds: float):
    cutoff = time.time() - older_than_seconds
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE created_at < ?", (cutoff,)).fetchall()
        return [dict(r) for r in rows]


def delete_job(job_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

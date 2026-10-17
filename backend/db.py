"""
SQLite database: connection + schema (Component 3).

Why SQLite: it's a single file, ships with Python (no install, no server),
and is plenty for a hackathon demo on one laptop.

Where the file lives:
    data/dharrakshak.sqlite3            (default, git-ignored)
    $DHARRAKSHAK_DB                     (override, e.g. tests use a temp file)

Tables:
    farmers         one row per farmer
    crops           a farmer's crop profile (F2)
    analyses        every leaf analysis, stored as validated contract JSON (F1–F4)
    loans           MOCK loan records per farmer (F5) — no bank integration
    loan_documents  required documents per loan + whether submitted (F5)

All reads/writes go through backend/repository.py, which converts rows to
the Pydantic models in shared/contract.py. Routes never write SQL.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "dharrakshak.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS farmers (
    farmer_id           TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    preferred_language  TEXT NOT NULL DEFAULT 'en',
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS crops (
    crop_id                 TEXT PRIMARY KEY,
    farmer_id               TEXT NOT NULL REFERENCES farmers(farmer_id) ON DELETE CASCADE,
    crop_type               TEXT NOT NULL,
    variety                 TEXT,
    sowing_date             TEXT NOT NULL,          -- ISO date, YYYY-MM-DD
    area_acres              REAL NOT NULL CHECK (area_acres > 0),
    location_name           TEXT NOT NULL,
    latitude                REAL NOT NULL,
    longitude               REAL NOT NULL,
    stage                   TEXT NOT NULL,
    expected_harvest_start  TEXT,
    expected_harvest_end    TEXT,
    yield_min_kg            REAL,
    yield_max_kg            REAL,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

-- The full AnalysisResult is kept as JSON (it is nested and already
-- validated by the contract). A few columns are copied out for queries.
CREATE TABLE IF NOT EXISTS analyses (
    analysis_id   TEXT PRIMARY KEY,
    crop_id       TEXT NOT NULL REFERENCES crops(crop_id) ON DELETE CASCADE,
    created_at    TEXT NOT NULL,                    -- ISO datetime
    top_label     TEXT NOT NULL,
    risk_level    TEXT NOT NULL,
    is_demo       INTEGER NOT NULL,
    result_json   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analyses_crop_time ON analyses (crop_id, created_at);

CREATE TABLE IF NOT EXISTS loans (
    loan_id                 TEXT PRIMARY KEY,
    farmer_id               TEXT NOT NULL REFERENCES farmers(farmer_id) ON DELETE CASCADE,
    loan_type               TEXT NOT NULL,
    display_name_json       TEXT NOT NULL,          -- LocalizedText as JSON
    lender_name             TEXT NOT NULL,
    status                  TEXT NOT NULL,
    sanctioned_amount_inr   INTEGER NOT NULL CHECK (sanctioned_amount_inr >= 0),
    outstanding_amount_inr  INTEGER NOT NULL CHECK (outstanding_amount_inr >= 0),
    next_due_date           TEXT,
    next_due_amount_inr     INTEGER,
    data_source             TEXT NOT NULL CHECK (data_source IN ('mock', 'farmer_entered'))
);

CREATE TABLE IF NOT EXISTS loan_documents (
    loan_id     TEXT NOT NULL REFERENCES loans(loan_id) ON DELETE CASCADE,
    code        TEXT NOT NULL,
    name_json   TEXT NOT NULL,                      -- LocalizedText as JSON
    submitted   INTEGER NOT NULL DEFAULT 0,
    position    INTEGER NOT NULL,                   -- display order
    PRIMARY KEY (loan_id, code)
);
"""


def db_path() -> Path:
    """Path of the database file (read each time so tests can override it)."""
    return Path(os.getenv("DHARRAKSHAK_DB", str(DEFAULT_DB_PATH)))


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, roll back on error, always close.

    Usage:
        with connect() as conn:
            conn.execute("SELECT ...")
    """
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row          # rows behave like dicts: row["crop_id"]
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite needs this per connection
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create any missing tables. Safe to call on every startup."""
    with connect() as conn:
        conn.executescript(SCHEMA)

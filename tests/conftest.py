"""
Shared test fixtures.

Every test gets its own empty SQLite file in a temp folder, so tests never
touch the real data/dharrakshak.sqlite3 and never affect each other.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def db_file(tmp_path, monkeypatch):
    """Point the backend at a fresh temporary database file."""
    path = tmp_path / "test.sqlite3"
    monkeypatch.setenv("DHARRAKSHAK_DB", str(path))
    return path


@pytest.fixture
def client(db_file):
    """A test client. `with` runs the app's startup (create tables + seed demo)."""
    with TestClient(app) as test_client:
        yield test_client

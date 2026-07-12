"""Shared fixtures. Every test runs against an isolated temp data directory so
the suite never touches the real `data/` and is fully hermetic and repeatable.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Make the project root importable (so `import backend...` works under pytest).
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAMPLE_CSV = (
    "region,month,revenue,units\n"
    "North,2026-01,120,10\n"
    "South,2026-01,90,8\n"
    "North,2026-02,150,12\n"
    "South,2026-02,110,9\n"
    "East,2026-01,70,6\n"
    "West,2026-02,200,15\n"
)


@pytest.fixture
def sample_df():
    from io import StringIO
    return pd.read_csv(StringIO(SAMPLE_CSV))


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """Point every on-disk path the backend writes to at a fresh temp dir."""
    from backend import storage, config, users
    import backend.main as main

    conv = tmp_path / "conversations"
    conv.mkdir()
    (tmp_path / "uploads").mkdir()
    (tmp_path / "exports").mkdir()

    monkeypatch.setattr(storage, "DATA_DIR", str(conv))
    monkeypatch.setattr(storage, "SHARES_PATH", str(tmp_path / "shares.json"))
    monkeypatch.setattr(config, "DATA_DIR", str(conv))
    monkeypatch.setattr(config, "_settings", {})
    monkeypatch.setattr(users, "USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(main, "UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(main, "EXPORTS_DIR", str(tmp_path / "exports"))
    monkeypatch.setattr(main, "_ANALYTICS_PATH", tmp_path / "analytics.jsonl")
    monkeypatch.setattr(main, "_SOURCES_PATH", tmp_path / "sources.json")
    # No global AI key, no proxy secret, no admin password by default.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("PROXY_SHARED_SECRET", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    # Fixed key-encryption secret so crypto is deterministic and never writes .env.
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-hermetic")
    monkeypatch.setattr("backend.crypto._secret_cache", None, raising=False)
    return tmp_path


@pytest.fixture
def client():
    """FastAPI TestClient over the real app (paths redirected by isolated_data)."""
    from fastapi.testclient import TestClient
    import backend.main as main
    return TestClient(main.app)


@pytest.fixture
def upload_csv(client):
    """Upload the sample dataset, return its file_id."""
    def _upload(csv: str = SAMPLE_CSV, name: str = "sales.csv"):
        r = client.post("/api/upload", files={"file": (name, csv.encode(), "text/csv")})
        assert r.status_code == 200, r.text
        return r.json()["file_id"]
    return _upload

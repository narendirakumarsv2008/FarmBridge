"""Pytest fixtures — run the suite against a throwaway SQLite database."""

import os
import tempfile

# Set these BEFORE importing config/app so config reads them at import time.
os.environ["ENVIRONMENT"] = "testing"
os.environ["DB_ENGINE"] = "sqlite"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["UPLOAD_FOLDER"] = os.path.join(tempfile.gettempdir(), "farmbridge_test_uploads")

import pytest  # noqa: E402

import config  # noqa: E402
from database import db  # noqa: E402
from app import app as flask_app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Fresh SQLite DB + test client per test."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(config.Config, "SQLITE_PATH", db_file)
    monkeypatch.setattr(config.Config, "DB_ENGINE", "sqlite")
    monkeypatch.setattr(config.Config, "ENVIRONMENT", "testing")
    monkeypatch.setattr(config, "UPLOAD_FOLDER", str(tmp_path / "uploads"))
    db.init_db(engine="sqlite", sqlite_path=db_file)
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


@pytest.fixture()
def farmer(client):
    """A logged-in farmer (returns the login payload)."""
    res = client.post("/api/auth/login", json={"name": "Farmer A", "phone": "9876543210"})
    data = res.get_json()
    return data["data"]


def make_listing(client, **overrides):
    payload = {
        "farmer_name": "Farmer A",
        "phone": "9876543210",
        "crop_name": "Tomato",
        "harvest_date": "2026-09-03",
        "quantity": "100",
        "price": "40",
        "location": "Kochi",
        "voice_transcript": "100 kg tomato at 40 rupees",
    }
    payload.update(overrides)
    return client.post("/api/listings", json=payload)

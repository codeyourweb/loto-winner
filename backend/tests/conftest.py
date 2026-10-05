"""Shared fixtures for the whole test suite."""

from __future__ import annotations

import pytest

from app import create_app
from app.config import ProductionConfig, TestConfig


@pytest.fixture()
def app(tmp_path):
    """Isolated test application, with its own temporary SQLite database."""

    class Cfg(TestConfig):
        DATABASE_PATH = str(tmp_path / "test.db")

    application = create_app(Cfg)
    yield application


@pytest.fixture()
def client(app):
    """Test HTTP client attached to the isolated application."""
    return app.test_client()


@pytest.fixture()
def production_app(tmp_path):
    """Application configured as in production (HSTS, secure cookies)."""

    class Cfg(ProductionConfig):
        DATABASE_PATH = str(tmp_path / "prod.db")
        SECRET_KEY = "prod-test-key"
        CORS_ORIGINS = ["https://loto-winner.example"]

    application = create_app(Cfg)
    yield application


@pytest.fixture()
def valid_payload():
    """Reusable valid JSON body."""
    return {"numbers": [1, 2, 3, 4, 5], "chance": 7, "persist": False}

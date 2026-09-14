import os
import tempfile

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient wired to a throwaway SQLite DB per test.

    DATA_DIR must be set before app.db is imported (it creates the engine
    at import time), so each test gets its own module import in a fresh
    subprocess-like state via importlib reload.
    """
    import importlib
    import sys

    data_dir = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("RESTORE_TOKEN", "test-token")

    for mod in [
        "app.main",
        "app.routes",
        "app.internal_routes",
        "app.backup",
        "app.services",
        "app.models",
        "app.db",
        "app",
    ]:
        sys.modules.pop(mod, None)

    from fastapi.testclient import TestClient

    main = importlib.import_module("app.main")
    with TestClient(main.app) as c:
        yield c

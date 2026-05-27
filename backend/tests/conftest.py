"""
Test configuration for the backend.

Sets an isolated DATA_DIR before importing the app so the JSON storage
writes to a temp folder, and exposes an authenticated client helper.
"""
import os
import tempfile

import pytest

# Must be set before importing the app (storage reads it at import).
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="finalytics_test_"))
os.environ.setdefault("SECRET_KEY", "test-secret")

from fastapi.testclient import TestClient  # noqa: E402
import main as main_module  # noqa: E402

main = main_module


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def auth_headers(client):
    """Register a fresh user and return Authorization headers."""
    import uuid
    username = "u_" + uuid.uuid4().hex[:8]
    r = client.post("/auth/register", json={"username": username, "password": "pw123456"})
    assert r.status_code == 200
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}

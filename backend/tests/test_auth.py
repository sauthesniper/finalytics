"""Auth, RBAC and token-economy tests."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_and_login(client):
    r = client.post("/auth/register", json={"username": "alice", "password": "secret12"})
    assert r.status_code == 200
    assert r.json()["tokens"] == 10

    r2 = client.post("/auth/login", json={"username": "alice", "password": "secret12"})
    assert r2.status_code == 200
    assert r2.json()["username"] == "alice"


def test_duplicate_register_rejected(client):
    client.post("/auth/register", json={"username": "bob", "password": "secret12"})
    r = client.post("/auth/register", json={"username": "bob", "password": "secret12"})
    assert r.status_code == 400


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "carol", "password": "secret12"})
    r = client.post("/auth/login", json={"username": "carol", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_auth(client, auth_headers):
    r = client.get("/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["role"] == "user"


def test_non_admin_cannot_list_users(client, auth_headers):
    r = client.get("/admin/users", headers=auth_headers)
    assert r.status_code == 403


def test_admin_can_list_users(client):
    login = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    token = login.json()["token"]
    r = client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_analyze_insufficient_tokens(client, auth_headers):
    # New user has 10 tokens; full set costs 11 -> should be rejected
    r = client.post("/analyze",
                    json={"cui": "14388248", "services": ["serp", "anaf", "intel", "berc"]},
                    headers=auth_headers)
    assert r.status_code == 402


def test_analyze_deducts_tokens(client, auth_headers):
    r = client.post("/analyze",
                    json={"cui": "14388248", "services": ["anaf"]},
                    headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["cost"] == 1
    assert body["remaining_tokens"] == 9

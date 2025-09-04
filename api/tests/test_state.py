from fastapi.testclient import TestClient

from api.main import app


def test_state_requires_auth():
    client = TestClient(app)
    r = client.get("/state")
    assert r.status_code == 401


def test_state_ok_with_token():
    client = TestClient(app)
    r = client.get("/state", headers={"Authorization": "Bearer dev"})
    assert r.status_code == 200
    body = r.json()
    assert "availability" in body and "mood" in body


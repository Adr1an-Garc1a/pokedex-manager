def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200


def test_collection_requires_auth(client):
    response = client.get("/api/v1/collection")
    assert response.status_code == 401

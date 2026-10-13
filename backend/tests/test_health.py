from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_service_name(client: TestClient) -> None:
    response = client.get("/health")

    assert response.json()["service"] == "warrantytrack-api"

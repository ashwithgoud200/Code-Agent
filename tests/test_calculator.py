"""Unit & Integration tests for Calculator Microservice."""
import pytest
from fastapi.testclient import TestClient

from app import app, OPS, STATE

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    STATE["version"] = "1.0"
    STATE["bug"] = False
    STATE["injected_latency"] = 0.0
    yield
    STATE["version"] = "1.0"
    STATE["bug"] = False
    STATE["injected_latency"] = 0.0


def test_basic_arithmetic():
    assert client.get("/calc/add?a=10&b=5").json()["result"] == 15.0
    assert client.get("/calc/sub?a=10&b=4").json()["result"] == 6.0
    assert client.get("/calc/mul?a=3&b=7").json()["result"] == 21.0
    assert client.get("/calc/div?a=20&b=4").json()["result"] == 5.0
    assert client.get("/calc/pow?a=2&b=3").json()["result"] == 8.0


def test_zero_division_returns_http_400():
    resp = client.get("/calc/div?a=10&b=0")
    assert resp.status_code == 400
    assert "division by zero" in resp.json()["detail"]


def test_unknown_operation_returns_http_404():
    resp = client.get("/calc/nonexistent?a=1&b=2")
    assert resp.status_code == 404
    assert "Unknown operation" in resp.json()["detail"]


def test_health_and_metrics():
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    data = health_resp.json()
    assert data["status"] == "ok"
    assert "add" in data["operations"]

    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert b"calc_requests_total" in metrics_resp.content


def test_admin_deploy_and_rollback():
    # Deploy v1.1
    deploy_res = client.post("/admin/deploy?version=1.1&bug=true")
    assert deploy_res.status_code == 200
    assert STATE["version"] == "1.1"
    assert STATE["bug"] is True

    # Health reflects degradation
    assert client.get("/health").json()["status"] == "degraded"

    # Rollback to v1.0
    rollback_res = client.post("/admin/rollback")
    assert rollback_res.status_code == 200
    assert rollback_res.json()["rolled_back_to"] == "1.0"
    assert STATE["version"] == "1.0"
    assert STATE["bug"] is False


def test_dynamic_feature_sqrt():
    if "sqrt" in OPS:
        res = client.get("/calc/sqrt?a=25")
        assert res.status_code == 200
        assert res.json()["result"] == 5.0

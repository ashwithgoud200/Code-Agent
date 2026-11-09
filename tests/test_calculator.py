"""Unit & Integration tests for Calculator Microservice."""
import os
import sys

# Ensure repository root is on sys.path for CI runners
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

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


def test_ui_root_endpoint_serves_html():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "OpsPilot Calculator" in resp.text


def test_remote_fault_latency_and_reset():
    resp = client.post("/admin/fault/latency?seconds=0.05")
    assert resp.status_code == 200
    assert STATE["injected_latency"] == 0.05
    assert client.get("/admin/fault/status").json()["injected_latency"] == 0.05
    assert client.get("/health").json()["status"] == "degraded"

    reset_resp = client.post("/admin/fault/reset")
    assert reset_resp.status_code == 200
    assert STATE["injected_latency"] == 0.0
    assert client.get("/health").json()["status"] == "ok"


def test_remote_fault_crash_mode():
    arm_resp = client.post("/admin/fault/crash?active=true&message=Simulated+Chaos+Crash")
    assert arm_resp.status_code == 200
    assert STATE["crash_mode"] is True

    calc_resp = client.get("/calc/add?a=2&b=3")
    assert calc_resp.status_code == 500
    assert "Simulated Chaos Crash" in calc_resp.json()["detail"]

    client.post("/admin/fault/reset")
    assert STATE["crash_mode"] is False
    assert client.get("/calc/add?a=2&b=3").status_code == 200


def test_remote_fault_cpu_and_memory():
    cpu_res = client.post("/admin/fault/cpu?duration_seconds=1&num_threads=1")
    assert cpu_res.status_code == 200
    assert cpu_res.json()["status"] == "started"

    mem_res = client.post("/admin/fault/memory?megabytes=10&duration_seconds=1")
    assert mem_res.status_code == 200
    assert mem_res.json()["status"] == "started"


def test_admin_deploy_feature_dynamically():
    snippet = 'OPS["cube"] = lambda a: a ** 3'
    resp = client.post("/admin/features/deploy", json={
        "op": "cube",
        "code_snippet": snippet,
        "feature_name": "Cube",
        "version": "1.2.0"
    })
    assert resp.status_code == 200
    assert "cube" in resp.json()["active_operations"]
    assert client.get("/calc/cube?a=3").json()["result"] == 27.0




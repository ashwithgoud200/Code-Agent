"""Unit & Integration tests for Cloud eCommerce Microservice."""
import os
import sys

# Ensure repository root is on sys.path for CI runners
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest
from fastapi.testclient import TestClient

from app import app, STATE, DYNAMIC_FEATURES, OPS

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    STATE["version"] = "1.0"
    STATE["bug"] = False
    STATE["injected_latency"] = 0.0
    STATE["crash_mode"] = False
    STATE["cart"].clear()
    yield
    STATE["version"] = "1.0"
    STATE["bug"] = False
    STATE["injected_latency"] = 0.0
    STATE["crash_mode"] = False
    STATE["cart"].clear()


def test_products_catalog():
    resp = client.get("/products")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 6
    assert any(p["id"] == "prod_1" for p in data["products"])

    # Test category filter
    resp_hw = client.get("/products?category=Hardware")
    assert resp_hw.status_code == 200
    assert all(p["category"] == "Hardware" for p in resp_hw.json()["products"])

    # Test single product detail
    prod_resp = client.get("/products/prod_1")
    assert prod_resp.status_code == 200
    assert prod_resp.json()["name"] == "DevOps Mechanical Keyboard"


def test_cart_workflow():
    # 1. Add item to cart
    add_resp = client.post("/cart/items", json={"product_id": "prod_1", "quantity": 2})
    assert add_resp.status_code == 200
    cart = add_resp.json()
    assert cart["item_count"] == 2
    assert cart["subtotal"] > 0

    # 2. Get cart
    get_cart = client.get("/cart").json()
    assert get_cart["item_count"] == 2

    # 3. Remove item from cart
    del_resp = client.delete("/cart/items/prod_1")
    assert del_resp.status_code == 200
    assert del_resp.json()["item_count"] == 0


def test_order_checkout_success():
    # Add items to cart
    client.post("/cart/items", json={"product_id": "prod_3", "quantity": 1})

    # Checkout
    order_req = {
        "customer_name": "Ashwith Goud",
        "customer_email": "ashwith@example.com",
        "shipping_address": "123 DevOps Way",
        "payment_method": "card",
    }
    checkout_res = client.post("/orders/checkout", json=order_req)
    assert checkout_res.status_code == 200
    order = checkout_res.json()["order"]
    assert order["status"] == "confirmed"
    assert order["total"] > 0

    # Cart should be cleared after checkout
    assert client.get("/cart").json()["item_count"] == 0

    # Order should exist in order history
    orders = client.get("/orders").json()
    assert orders["total"] >= 1


def test_checkout_deployment_regression_bug():
    client.post("/cart/items", json={"product_id": "prod_2", "quantity": 1})

    # Deploy v1.1 regression bug
    deploy_res = client.post("/admin/deploy?version=1.1&bug=true")
    assert deploy_res.status_code == 200
    assert STATE["version"] == "1.1"
    assert STATE["bug"] is True
    assert client.get("/health").json()["status"] == "degraded"

    # Checkout fails with 500 Payment Gateway Error
    checkout_fail = client.post("/orders/checkout", json={"customer_name": "Test Customer"})
    assert checkout_fail.status_code == 500
    assert "Payment Gateway Integration Error" in checkout_fail.json()["detail"]

    # Rollback to v1.0
    rollback_res = client.post("/admin/rollback")
    assert rollback_res.status_code == 200
    assert rollback_res.json()["rolled_back_to"] == "1.0"
    assert STATE["bug"] is False
    assert client.get("/health").json()["status"] == "ok"

    # Checkout now succeeds
    checkout_ok = client.post("/orders/checkout", json={"customer_name": "Test Customer"})
    assert checkout_ok.status_code == 200
    assert checkout_ok.json()["status"] == "confirmed"


def test_coupon_dynamic_feature():
    client.post("/cart/items", json={"product_id": "prod_1", "quantity": 1})
    cart_with_coupon = client.get("/cart?coupon_code=DEVOPS20").json()
    assert cart_with_coupon["discount"] > 0


def test_health_and_metrics():
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["service"] == "ecommerce-storefront"

    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert b"ecommerce_http_requests_total" in metrics_resp.content


def test_remote_fault_latency_and_crash():
    # Latency test
    client.post("/admin/fault/latency?seconds=0.02")
    assert STATE["injected_latency"] == 0.02

    # Crash mode test
    client.post("/admin/fault/crash?active=true&message=Chaos+Simulated+Error")
    assert STATE["crash_mode"] is True
    assert client.get("/products").status_code == 500

    # Reset
    client.post("/admin/fault/reset")
    assert STATE["crash_mode"] is False
    assert client.get("/products").status_code == 200


def test_legacy_calc_compatibility():
    res = client.get("/calc/add?a=10&b=20")
    assert res.status_code == 200
    assert res.json()["result"] == 30.0


def test_ui_root_endpoint_serves_html():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")

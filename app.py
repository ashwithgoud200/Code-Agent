"""Cloud eCommerce Microservice Application.

Target production application managed, monitored, and automated by the DevOps Multi-Agent System.
Features:
- Product Catalog & Search (/products)
- Shopping Cart Management (/cart, /cart/items)
- Order Checkout & Inventory Engine (/orders/checkout)
- Dynamic Feature Plugins (Coupons, Tax, Shipping in features/*.py)
- Real Business & System Prometheus Metrics (/metrics)
- Health check and liveness probes (/health)
- Version history and rollback controls (/admin/*)
- Chaos & Fault Injection Hooks (/admin/fault/*)
- Interactive Storefront Web UI (/)
"""
from __future__ import annotations

import glob
import importlib.util
import inspect
import json
import logging
import math
import os
import sys
import threading
import time
import uuid
from typing import Any
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.getenv("ECOMMERCE_LOG_PATH", os.path.join(ROOT, "logs", "app.log"))
os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)

logger = logging.getLogger("ecommerce")
logger.setLevel(logging.INFO)
if not logger.handlers:
    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(console_handler)

# =========================================================================
# Prometheus Metrics (Business + System Telemetry)
# =========================================================================
HTTP_REQUESTS_TOTAL = Counter(
    "ecommerce_http_requests_total",
    "Total HTTP requests handled by eCommerce service",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "ecommerce_request_duration_seconds",
    "eCommerce HTTP request latency in seconds",
    ["endpoint"],
)
ORDERS_TOTAL = Counter(
    "ecommerce_orders_total",
    "Total eCommerce checkout orders placed",
    ["status", "payment_method"],
)
REVENUE_TOTAL = Counter(
    "ecommerce_revenue_usd_total",
    "Total gross revenue generated in USD",
)
CART_ITEMS_GAUGE = Gauge(
    "ecommerce_cart_items_total",
    "Current total items in active shopping carts",
)
INVENTORY_STOCK_GAUGE = Gauge(
    "ecommerce_inventory_stock",
    "Current product stock levels in inventory",
    ["product_id", "category"],
)

# Legacy alias metric to preserve existing Prometheus dashboard scrapes
REQ_TOTAL = Counter("calc_requests_total", "Legacy requests counter", ["op", "status"])

# =========================================================================
# Product Catalog Data
# =========================================================================
INITIAL_PRODUCTS: dict[str, dict[str, Any]] = {
    "prod_1": {
        "id": "prod_1",
        "name": "DevOps Mechanical Keyboard",
        "category": "Hardware",
        "price": 149.99,
        "stock": 25,
        "rating": 4.9,
        "description": "Hot-swappable RGB mechanical keyboard tuned for terminal velocity.",
        "badge": "Bestseller",
    },
    "prod_2": {
        "id": "prod_2",
        "name": "Noise-Cancelling Cloud Headphones",
        "category": "Audio",
        "price": 199.50,
        "stock": 18,
        "rating": 4.8,
        "description": "Active ANC wireless headset for zero-distraction incident debugging.",
        "badge": "Popular",
    },
    "prod_3": {
        "id": "prod_3",
        "name": "Kubernetes Cluster Plushie",
        "category": "Swag",
        "price": 29.00,
        "stock": 60,
        "rating": 5.0,
        "description": "Soft plushie container orchestrator to keep your desk pod healthy.",
        "badge": "Fan Favorite",
    },
    "prod_4": {
        "id": "prod_4",
        "name": "Ultra-Wide 4K Developer Monitor",
        "category": "Displays",
        "price": 499.00,
        "stock": 10,
        "rating": 4.7,
        "description": "34-inch curved panoramic display for logs, metrics, and IDEs side-by-side.",
        "badge": "Top Rated",
    },
    "prod_5": {
        "id": "prod_5",
        "name": "Thermal Ergonomic Desk Chair",
        "category": "Furniture",
        "price": 349.00,
        "stock": 14,
        "rating": 4.6,
        "description": "Breathable mesh posture support engineered for long on-call rotations.",
        "badge": "Essential",
    },
    "prod_6": {
        "id": "prod_6",
        "name": "Docker Container Coffee Mug",
        "category": "Swag",
        "price": 19.99,
        "stock": 100,
        "rating": 4.9,
        "description": "Insulated stainless steel mug that guarantees containerized caffeine delivery.",
        "badge": "New",
    },
}

# Runtime In-Memory State
STATE: dict[str, Any] = {
    "version": "1.0",
    "bug": False,  # If true, /orders/checkout fails with 500 Payment Gateway Error
    "history": [{"version": "1.0", "ts": time.time()}],
    "injected_latency": 0.0,
    "crash_mode": False,
    "crash_message": "Unhandled runtime crash in eCommerce service",
    "products": dict(INITIAL_PRODUCTS),
    "cart": {},  # product_id -> quantity
    "orders": [],
}

# Sync initial stock levels to Prometheus
for p in STATE["products"].values():
    INVENTORY_STOCK_GAUGE.labels(product_id=p["id"], category=p["category"]).set(p["stock"])

# Dynamic Feature Plugins registry
DYNAMIC_FEATURES: dict[str, Any] = {}
OPS: dict[str, Any] = {  # Backward compatibility for arithmetic ops
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "div": lambda a, b: a / b if b != 0 else (_ for _ in ()).throw(ZeroDivisionError("division by zero")),
    "pow": lambda a, b: a ** b,
}


def _load_dynamic_features():
    """Discover and register features dynamically generated in features/*.py."""
    features_dir = os.path.join(ROOT, "features")
    if not os.path.isdir(features_dir):
        return
    for filepath in glob.glob(os.path.join(features_dir, "*.py")):
        filename = os.path.basename(filepath)
        if filename.startswith("_"):
            continue
        feat_name = os.path.splitext(filename)[0]
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                code_content = f.read()
            local_scope: dict[str, Any] = {
                "OPS": OPS,
                "DYNAMIC_FEATURES": DYNAMIC_FEATURES,
                "math": math,
                "ZeroDivisionError": ZeroDivisionError,
                "ValueError": ValueError,
            }
            exec(code_content, local_scope)
            logger.info("Loaded dynamic feature plugin: %s from %s", feat_name, filename)
        except Exception as exc:
            logger.warning("Failed to load feature %s: %s", feat_name, exc)


_load_dynamic_features()


def log_event(level: str, **kwargs):
    entry = {"ts": time.time(), "level": level, "service": "ecommerce-storefront", **kwargs}
    logger.info(json.dumps(entry))


# =========================================================================
# FastAPI Application & Middleware
# =========================================================================
app = FastAPI(
    title="Cloud eCommerce Microservice",
    description="Target production store managed, monitored, and automated by DevOps Multi-Agent System.",
    version="1.0.0",
)

STATIC_DIR = os.path.join(ROOT, "static")
if os.path.isdir(STATIC_DIR):
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    start = time.perf_counter()
    trace_id = request.headers.get("X-Trace-ID") or uuid.uuid4().hex
    request.state.trace_id = trace_id

    # Chaos Latency Injection
    latency = float(STATE.get("injected_latency", 0.0))
    if latency > 0:
        time.sleep(latency)

    # Chaos Crash Mode Check
    if STATE.get("crash_mode") and not request.url.path.startswith("/admin"):
        msg = str(STATE.get("crash_message", "Unhandled runtime crash in eCommerce service"))
        log_event("ERROR", endpoint=request.url.path, msg=msg)
        HTTP_REQUESTS_TOTAL.labels(method=request.method, endpoint=request.url.path, status="500").inc()
        return Response(content=json.dumps({"detail": msg}), status_code=500, media_type="application/json")

    try:
        response = await call_next(request)
        status_str = str(response.status_code)
        response.headers["X-Trace-ID"] = trace_id
        HTTP_REQUESTS_TOTAL.labels(method=request.method, endpoint=request.url.path, status=status_str).inc()
        return response
    except Exception as exc:
        HTTP_REQUESTS_TOTAL.labels(method=request.method, endpoint=request.url.path, status="500").inc()
        raise exc
    finally:
        duration = time.perf_counter() - start
        REQUEST_LATENCY.labels(endpoint=request.url.path).observe(duration)


# =========================================================================
# Storefront UI & Static Files
# =========================================================================
@app.get("/", summary="Interactive eCommerce Storefront UI")
def serve_storefront_ui():
    index_file = os.path.join(ROOT, "static", "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)
    return {
        "status": "ok",
        "service": "ecommerce-storefront",
        "version": STATE["version"],
        "endpoints": ["/products", "/cart", "/orders/checkout", "/health", "/metrics"],
    }


# =========================================================================
# Product Catalog API
# =========================================================================
@app.get("/products", summary="List all products with category and search filter")
def list_products(category: str | None = None, search: str | None = None):
    prods = list(STATE["products"].values())
    if category and category.lower() != "all":
        prods = [p for p in prods if p["category"].lower() == category.lower()]
    if search:
        s = search.lower()
        prods = [p for p in prods if s in p["name"].lower() or s in p["description"].lower()]
    return {
        "total": len(prods),
        "products": prods,
        "version": STATE["version"],
    }


@app.get("/products/{product_id}", summary="Get product details")
def get_product(product_id: str):
    if product_id not in STATE["products"]:
        raise HTTPException(404, f"Product '{product_id}' not found.")
    return STATE["products"][product_id]


# =========================================================================
# Shopping Cart API
# =========================================================================
class CartItemRequest(BaseModel):
    product_id: str = Field(..., description="Product ID to add or update")
    quantity: int = Field(default=1, ge=1, le=10, description="Quantity to set")


@app.get("/cart", summary="Get current shopping cart contents and calculated total")
def get_cart(coupon_code: str | None = None):
    items = []
    subtotal = 0.0
    for pid, qty in STATE["cart"].items():
        prod = STATE["products"].get(pid)
        if prod:
            line_total = round(prod["price"] * qty, 2)
            subtotal += line_total
            items.append({
                "product_id": pid,
                "name": prod["name"],
                "price": prod["price"],
                "quantity": qty,
                "line_total": line_total,
                "stock": prod["stock"],
            })

    # Calculate discounts via dynamic feature plugins if available
    discount = 0.0
    discount_label = None
    if coupon_code and "coupon" in DYNAMIC_FEATURES:
        coupon_fn = DYNAMIC_FEATURES["coupon"]
        try:
            discount = float(coupon_fn(coupon_code, subtotal))
            discount_label = f"Coupon {coupon_code.upper()}"
        except Exception:
            discount = 0.0

    shipping = 0.0 if subtotal >= 100.0 or subtotal == 0 else 9.99
    tax = round(max(0.0, subtotal - discount) * 0.0825, 2)
    grand_total = round(max(0.0, subtotal - discount) + shipping + tax, 2)

    return {
        "items": items,
        "item_count": sum(STATE["cart"].values()),
        "subtotal": round(subtotal, 2),
        "discount": round(discount, 2),
        "discount_label": discount_label,
        "shipping": shipping,
        "tax": tax,
        "total": grand_total,
    }


@app.post("/cart/items", summary="Add or update item in shopping cart")
def add_cart_item(req: CartItemRequest):
    if req.product_id not in STATE["products"]:
        raise HTTPException(404, f"Product '{req.product_id}' not found.")
    prod = STATE["products"][req.product_id]
    if prod["stock"] < req.quantity:
        raise HTTPException(400, f"Insufficient stock for '{prod['name']}'. Available: {prod['stock']}")

    STATE["cart"][req.product_id] = req.quantity
    CART_ITEMS_GAUGE.set(sum(STATE["cart"].values()))
    log_event("INFO", event="cart_updated", product_id=req.product_id, quantity=req.quantity)
    return get_cart()


@app.delete("/cart/items/{product_id}", summary="Remove item from shopping cart")
def remove_cart_item(product_id: str):
    if product_id in STATE["cart"]:
        del STATE["cart"][product_id]
        CART_ITEMS_GAUGE.set(sum(STATE["cart"].values()))
        log_event("INFO", event="cart_item_removed", product_id=product_id)
    return get_cart()


@app.delete("/cart", summary="Clear entire shopping cart")
def clear_cart():
    STATE["cart"].clear()
    CART_ITEMS_GAUGE.set(0)
    return {"status": "cleared", "items": [], "total": 0.0}


# =========================================================================
# Order Checkout API
# =========================================================================
class CheckoutRequest(BaseModel):
    customer_name: str = Field(default="Ashwith Goud", description="Customer full name")
    customer_email: str = Field(default="ashwith@devops.local", description="Customer email")
    shipping_address: str = Field(default="123 Cloud Engineer Way, Tech City", description="Shipping address")
    payment_method: str = Field(default="card", description="Payment method: card, stripe, paypal")
    coupon_code: str | None = Field(default=None, description="Optional discount code")


@app.post("/orders/checkout", summary="Execute order checkout and charge payment")
def checkout_order(req: CheckoutRequest):
    if not STATE["cart"]:
        raise HTTPException(400, "Shopping cart is empty. Add products before checkout.")

    # ---------------------------------------------------------------------
    # Synthetic Deployment Regression Bug: v1.1 Payment Gateway Error
    # ---------------------------------------------------------------------
    if STATE.get("bug"):
        err_msg = f"v{STATE['version']} regression: Payment Gateway Integration Error (504 Gateway Timeout connecting to Stripe)"
        log_event("ERROR", event="checkout_crashed", error=err_msg, version=STATE["version"])
        ORDERS_TOTAL.labels(status="failed", payment_method=req.payment_method).inc()
        raise HTTPException(500, err_msg)

    # Validate inventory & prepare line items
    cart_summary = get_cart(coupon_code=req.coupon_code)
    order_items = []
    for item in cart_summary["items"]:
        prod = STATE["products"][item["product_id"]]
        if prod["stock"] < item["quantity"]:
            raise HTTPException(400, f"Stock depleted for '{prod['name']}' during checkout.")
        # Deduct stock
        prod["stock"] -= item["quantity"]
        INVENTORY_STOCK_GAUGE.labels(product_id=prod["id"], category=prod["category"]).set(prod["stock"])
        order_items.append(dict(item))

    order_id = f"ord-{uuid.uuid4().hex[:8]}"
    order_record = {
        "order_id": order_id,
        "customer_name": req.customer_name,
        "customer_email": req.customer_email,
        "items": order_items,
        "item_count": cart_summary["item_count"],
        "subtotal": cart_summary["subtotal"],
        "discount": cart_summary["discount"],
        "shipping": cart_summary["shipping"],
        "tax": cart_summary["tax"],
        "total": cart_summary["total"],
        "payment_method": req.payment_method,
        "status": "confirmed",
        "version": STATE["version"],
        "created_at": time.time(),
    }

    STATE["orders"].append(order_record)
    STATE["cart"].clear()
    CART_ITEMS_GAUGE.set(0)

    ORDERS_TOTAL.labels(status="completed", payment_method=req.payment_method).inc()
    REVENUE_TOTAL.inc(order_record["total"])
    log_event("INFO", event="order_completed", order_id=order_id, total=order_record["total"])

    return {
        "status": "confirmed",
        "order_id": order_id,
        "order": order_record,
        "message": f"Order {order_id} placed successfully! Thank you for your purchase.",
    }


@app.get("/orders", summary="Get recent order history")
def list_orders():
    return {
        "total": len(STATE["orders"]),
        "orders": list(reversed(STATE["orders"][-20:])),
    }


@app.get("/orders/{order_id}", summary="Get order details by ID")
def get_order(order_id: str):
    for o in STATE["orders"]:
        if o["order_id"] == order_id:
            return o
    raise HTTPException(404, f"Order '{order_id}' not found.")


# =========================================================================
# Backward Compatibility Arithmetic API
# =========================================================================
@app.get("/calc/{op}", summary="Legacy arithmetic endpoint")
def legacy_calc(op: str, a: float, b: float = 0.0):
    if op not in OPS:
        raise HTTPException(404, f"Unknown operation '{op}'.")
    if STATE.get("bug") and op == "div":
        raise HTTPException(500, f"v{STATE['version']} regression: div handler crashed")
    fn = OPS[op]
    sig = inspect.signature(fn)
    res = fn(a) if len(sig.parameters) == 1 else fn(a, b)
    REQ_TOTAL.labels(op, "ok").inc()
    return {"op": op, "result": res, "version": STATE["version"]}


# =========================================================================
# Health & Prometheus Metrics Endpoints
# =========================================================================
@app.get("/health", summary="Liveness & Readiness probe")
def health():
    is_degraded = (
        bool(STATE.get("bug"))
        or bool(STATE.get("crash_mode"))
        or float(STATE.get("injected_latency", 0.0)) > 0
    )
    return {
        "status": "degraded" if is_degraded else "ok",
        "service": "ecommerce-storefront",
        "version": STATE["version"],
        "catalog_size": len(STATE["products"]),
        "orders_count": len(STATE["orders"]),
        "cart_item_count": sum(STATE["cart"].values()),
        "faults": {
            "bug": STATE.get("bug", False),
            "crash_mode": STATE.get("crash_mode", False),
            "injected_latency": STATE.get("injected_latency", 0.0),
        },
    }


@app.get("/metrics", summary="Prometheus scrape endpoint")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# =========================================================================
# Administration & Version Control Endpoints
# =========================================================================
@app.get("/admin/version", summary="Get deployment version history")
def get_version():
    return {
        "version": STATE["version"],
        "history": STATE["history"],
        "bug": STATE.get("bug", False),
        "service": "ecommerce-storefront",
    }


@app.post("/admin/deploy", summary="Deploy a specific version")
def deploy(version: str, bug: bool = False):
    STATE["version"] = version
    STATE["bug"] = bug
    STATE["history"].append({"version": version, "bug": bug, "ts": time.time()})
    log_event("INFO", msg=f"deployed v{version}", bug=bug)
    return {"deployed": version, "bug": bug}


@app.post("/admin/rollback", summary="Rollback to previous version")
def rollback():
    prev = STATE["history"][-2]["version"] if len(STATE["history"]) > 1 else "1.0"
    STATE["version"] = prev
    STATE["bug"] = False
    STATE["history"].append({"version": prev, "bug": False, "ts": time.time()})
    log_event("INFO", msg=f"rolled back to v{prev}")
    return {"rolled_back_to": prev}


# =========================================================================
# Remote Fault Injection & Chaos Endpoints
# =========================================================================
def _run_cpu_stress(duration_seconds: int = 15, num_threads: int = 2):
    stop_event = threading.Event()
    def _worker():
        end = time.time() + duration_seconds
        while not stop_event.is_set() and time.time() < end:
            _ = [i * i for i in range(1000)]
    threads = [threading.Thread(target=_worker, daemon=True) for _ in range(min(num_threads, 4))]
    for t in threads:
        t.start()


def _run_memory_stress(megabytes: int = 150, duration_seconds: int = 15):
    def _worker():
        try:
            chunks = [bytearray(1024 * 1024) for _ in range(min(megabytes, 300))]
            time.sleep(duration_seconds)
            del chunks
        except Exception:
            pass
    t = threading.Thread(target=_worker, daemon=True)
    t.start()


@app.get("/admin/fault/status", summary="Get active fault injection state")
def fault_status():
    return {
        "status": "ok",
        "version": STATE["version"],
        "bug": STATE.get("bug", False),
        "crash_mode": STATE.get("crash_mode", False),
        "crash_message": STATE.get("crash_message", ""),
        "injected_latency": STATE.get("injected_latency", 0.0),
    }


@app.post("/admin/fault/latency", summary="Inject artificial latency")
def set_fault_latency(seconds: float = 0.45):
    delay = max(0.0, min(float(seconds), 10.0))
    STATE["injected_latency"] = delay
    log_event("WARN", msg=f"fault latency updated: {delay}s")
    return {"status": "updated", "injected_latency": delay}


@app.post("/admin/fault/crash", summary="Arm or disarm unhandled crash mode")
def set_fault_crash(active: bool = True, message: str = "Unhandled runtime crash in eCommerce service"):
    STATE["crash_mode"] = bool(active)
    STATE["crash_message"] = str(message)
    log_event("WARN", msg=f"crash mode armed={active}: {message}")
    return {"status": "updated", "crash_mode": active, "message": message}


@app.post("/admin/fault/cpu", summary="Trigger CPU stress worker threads")
def trigger_cpu_fault(duration_seconds: int = 15, num_threads: int = 2):
    dur = max(1, min(duration_seconds, 60))
    threads = max(1, min(num_threads, 4))
    _run_cpu_stress(duration_seconds=dur, num_threads=threads)
    log_event("WARN", msg=f"cpu stress started: {threads} threads for {dur}s")
    return {"status": "started", "duration_seconds": dur, "threads": threads}


@app.post("/admin/fault/memory", summary="Trigger memory pressure allocation")
def trigger_memory_fault(megabytes: int = 150, duration_seconds: int = 15):
    mb = max(10, min(megabytes, 300))
    dur = max(1, min(duration_seconds, 60))
    _run_memory_stress(megabytes=mb, duration_seconds=dur)
    log_event("WARN", msg=f"memory stress started: {mb}MB for {dur}s")
    return {"status": "started", "megabytes": mb, "duration_seconds": dur}


@app.post("/admin/fault/reset", summary="Reset all injected faults")
def reset_all_faults():
    STATE["injected_latency"] = 0.0
    STATE["crash_mode"] = False
    STATE["bug"] = False
    STATE["crash_message"] = ""
    log_event("INFO", msg="all faults cleared and reset to healthy")
    return {"status": "cleared", "faults": {"bug": False, "crash_mode": False, "injected_latency": 0.0}}


# =========================================================================
# Dynamic Feature Deployment API
# =========================================================================
class FeatureDeployPayload(BaseModel):
    op: str
    code_snippet: str
    feature_name: str | None = None
    version: str | None = None


@app.post("/admin/features/deploy", summary="Deploy a new feature operator dynamically")
def admin_deploy_feature(payload: FeatureDeployPayload):
    feat_clean = payload.op.lower().strip()
    deploy_env = {
        "OPS": OPS,
        "DYNAMIC_FEATURES": DYNAMIC_FEATURES,
        "math": math,
        "ZeroDivisionError": ZeroDivisionError,
        "ValueError": ValueError,
    }
    try:
        exec(payload.code_snippet, deploy_env)
    except Exception as exc:
        raise HTTPException(500, f"Failed to activate feature '{feat_clean}': {exc}")

    features_dir = os.path.join(ROOT, "features")
    os.makedirs(features_dir, exist_ok=True)
    feature_file = os.path.join(features_dir, f"{feat_clean}.py")
    try:
        with open(feature_file, "w", encoding="utf-8") as f:
            f.write(
                f'"""{payload.feature_name or feat_clean} dynamic eCommerce feature plugin."""\n'
                f"import math\n\n"
                f"{payload.code_snippet}\n"
            )
    except Exception as e:
        logger.warning("Could not persist feature file: %s", e)

    if payload.version:
        STATE["version"] = payload.version
        STATE["history"].append({"version": payload.version, "ts": time.time(), "feature": feat_clean})

    log_event("INFO", msg=f"Feature {feat_clean} deployed to live microservice", feature=feat_clean)
    return {
        "status": "deployed",
        "feature": feat_clean,
        "feature_name": payload.feature_name,
        "version": STATE["version"],
        "active_features": list(DYNAMIC_FEATURES.keys()),
        "active_operations": sorted(list(OPS.keys())),
    }


@app.post("/admin/features/reload", summary="Reload dynamic features from disk")
def reload_features():
    _load_dynamic_features()
    return {
        "status": "reloaded",
        "active_features": list(DYNAMIC_FEATURES.keys()),
        "active_operations": sorted(list(OPS.keys())),
    }

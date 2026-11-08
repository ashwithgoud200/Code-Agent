"""Calculator Microservice Application.

Target application managed, monitored, and automated by the DevOps Multi-Agent System.
Features:
- Pure REST mathematical operations (/calc/{op})
- Dynamic feature plugin auto-loader (loads features/*.py synthesized by Code Agent)
- Prometheus metrics (/metrics)
- Health check and liveness probes (/health)
- Version history and rollback controls (/admin/*)
- Structured JSON logging with trace context
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
import time
import uuid
from typing import Any
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.getenv("CALC_LOG_PATH", os.path.join(ROOT, "logs", "app.log"))
os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)

logger = logging.getLogger("calculator")
logger.setLevel(logging.INFO)
if not logger.handlers:
    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(console_handler)

# Prometheus Metrics
REQ_TOTAL = Counter("calc_requests_total", "Total calculator requests", ["op", "status"])
REQ_LATENCY = Histogram("calc_latency_seconds", "Calculator request latency in seconds", ["op"])

# Core Built-in Operators
OPS: dict[str, Any] = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "div": lambda a, b: a / b if b != 0 else (_ for _ in ()).throw(ZeroDivisionError("float division by zero")),
    "pow": lambda a, b: a ** b,
}

# Runtime State
STATE: dict[str, Any] = {
    "version": "1.0",
    "bug": False,
    "history": [{"version": "1.0", "ts": time.time()}],
    "injected_latency": 0.0,
}


def _load_dynamic_features():
    """Discover and register features dynamically generated in the features/ directory."""
    features_dir = os.path.join(ROOT, "features")
    if not os.path.isdir(features_dir):
        return
    for filepath in glob.glob(os.path.join(features_dir, "*.py")):
        filename = os.path.basename(filepath)
        if filename.startswith("_"):
            continue
        op_name = os.path.splitext(filename)[0]
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                code_content = f.read()
            local_scope: dict[str, Any] = {"OPS": OPS, "math": math, "ZeroDivisionError": ZeroDivisionError, "ValueError": ValueError}
            exec(code_content, local_scope)
            logger.info("Loaded custom feature plugin: %s from %s", op_name, filename)
        except Exception as exc:
            logger.warning("Failed to load feature %s: %s", op_name, exc)


_load_dynamic_features()


def log_event(level: str, **kwargs):
    entry = {"ts": time.time(), "level": level, "service": "calculator", **kwargs}
    logger.info(json.dumps(entry))


app = FastAPI(
    title="Calculator Microservice",
    description="Target production application for DevOps AI Multi-Agent automation & monitoring.",
    version="1.0.0",
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    trace_id = request.headers.get("X-Trace-ID") or uuid.uuid4().hex
    request.state.trace_id = trace_id
    try:
        response = await call_next(request)
        return response
    finally:
        pass


@app.get("/calc/{op}", summary="Execute calculation operation")
def calculate(op: str, a: float, b: float = 0.0):
    if op not in OPS:
        raise HTTPException(404, f"Unknown operation '{op}'. Active operations: {sorted(list(OPS.keys()))}")

    # Latency injection check
    latency = float(STATE.get("injected_latency", 0.0))
    if latency > 0:
        time.sleep(latency)

    # Bug simulation check
    if STATE.get("bug") and op == "div":
        log_event("ERROR", op=op, msg=f"v{STATE['version']} regression: div handler crashed")
        REQ_TOTAL.labels(op, "error").inc()
        raise HTTPException(500, f"v{STATE['version']} regression: div handler crashed")

    start = time.time()
    try:
        fn = OPS[op]
        sig = inspect.signature(fn)
        if len(sig.parameters) == 1:
            result = fn(a)
        else:
            result = fn(a, b)

        REQ_TOTAL.labels(op, "ok").inc()
        log_event("INFO", op=op, a=a, b=b, result=result, version=STATE["version"])
        return {"op": op, "result": result, "version": STATE["version"]}
    except ZeroDivisionError:
        REQ_TOTAL.labels(op, "client_error").inc()
        log_event("WARN", op=op, msg="division by zero (user input)")
        raise HTTPException(400, "division by zero")
    except ValueError as ve:
        REQ_TOTAL.labels(op, "client_error").inc()
        log_event("WARN", op=op, msg=str(ve))
        raise HTTPException(400, str(ve))
    except Exception as exc:
        REQ_TOTAL.labels(op, "error").inc()
        log_event("ERROR", op=op, msg=str(exc), version=STATE["version"])
        raise HTTPException(500, str(exc))
    finally:
        REQ_LATENCY.labels(op).observe(time.time() - start)


@app.get("/health", summary="Liveness & Readiness probe")
def health():
    return {
        "status": "degraded" if STATE.get("bug") else "ok",
        "service": "calculator",
        "version": STATE["version"],
        "active_operations": len(OPS),
        "operations": sorted(list(OPS.keys())),
    }


@app.get("/metrics", summary="Prometheus scrape endpoint")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/admin/version", summary="Get deployment version history")
def get_version():
    return {"version": STATE["version"], "history": STATE["history"], "bug": STATE.get("bug", False)}


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


@app.post("/admin/features/reload", summary="Reload dynamic features from disk")
def reload_features():
    _load_dynamic_features()
    return {"status": "reloaded", "active_operations": sorted(list(OPS.keys()))}

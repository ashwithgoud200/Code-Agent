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
import threading
import time
import uuid
from typing import Any
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
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
    "crash_mode": False,
    "crash_message": "Unhandled runtime crash in Calculator service",
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

STATIC_DIR = os.path.join(ROOT, "static")
if os.path.isdir(STATIC_DIR):
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", summary="Interactive Calculator Web UI")
def serve_calculator_ui():
    index_file = os.path.join(ROOT, "static", "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)
    return {
        "status": "ok",
        "service": "calculator",
        "version": STATE["version"],
        "endpoints": ["/calc/{op}", "/health", "/metrics", "/docs"],
    }


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

    # Crash mode simulation check
    if STATE.get("crash_mode"):
        crash_msg = str(STATE.get("crash_message", "Unhandled runtime crash in Calculator service"))
        log_event("ERROR", op=op, msg=crash_msg)
        REQ_TOTAL.labels(op, "error").inc()
        raise HTTPException(500, crash_msg)

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
    is_degraded = (
        bool(STATE.get("bug"))
        or bool(STATE.get("crash_mode"))
        or float(STATE.get("injected_latency", 0.0)) > 0
    )
    return {
        "status": "degraded" if is_degraded else "ok",
        "service": "calculator",
        "version": STATE["version"],
        "active_operations": len(OPS),
        "operations": sorted(list(OPS.keys())),
        "faults": {
            "bug": STATE.get("bug", False),
            "crash_mode": STATE.get("crash_mode", False),
            "injected_latency": STATE.get("injected_latency", 0.0),
        },
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
def set_fault_crash(active: bool = True, message: str = "Unhandled runtime crash in Calculator service"):
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



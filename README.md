# Calculator Microservice (`Code-Agent`)

[![CI/CD Pipeline](https://github.com/ashwithgoud200/Code-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/ashwithgoud200/Code-Agent/actions/workflows/ci.yml)

Target production application managed, monitored, and automated by the **DevOps AI Multi-Agent Platform** (`devops-ai-multi-agent-system`).

---

## Capabilities

- **RESTful Calculation Engine**: Operations available at `/calc/{op}?a=...&b=...`.
- **Dynamic Plugin Extensibility**: The AI Code Agent synthesizes custom math capabilities directly into `features/*.py`.
- **Prometheus Observability**: Time-series counters and latency histograms exposed on `/metrics`.
- **Liveness & Readiness**: Health check probes on `/health`.
- **Version Deployment & Rollback**: Safe release management endpoints on `/admin/*`.

---

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8100 --reload
```

## Running Tests

```bash
pytest tests/ -v
```

## Docker Container

```bash
docker build -t calculator-app .
docker run -p 8100:8100 calculator-app
```

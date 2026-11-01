# Elastic Document Intelligence Platform

[![CI Quality Gate](https://img.shields.io/badge/CI%20Gate-Passing-success)](.github/workflows/ci.yml)
[![Docling Version](https://img.shields.io/badge/Docling-v2-blue)](https://github.com/DS4SD/docling)
[![MLflow](https://img.shields.io/badge/MLflow-Tracking-orange)](evaluation/evaluate.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An enterprise-ready, asynchronous document conversion and intelligence platform demonstrating **asynchronous microservices**, **event-driven autoscaling**, **MLOps evaluation without retraining**, **reliability engineering**, and **cloud-native operations**.

---

## 🏛️ System Architecture

```mermaid
flowchart LR
    classDef clientStyle fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#01579b;
    classDef apiStyle fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20;
    classDef queueStyle fill:#ffebee,stroke:#d32f2f,stroke-width:2px,color:#b71c1c;
    classDef workerStyle fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100;
    classDef opsStyle fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c;
    classDef obsStyle fill:#fffde7,stroke:#fbc02d,stroke-width:2px,color:#f57f17;

    subgraph Clients ["Clients & Triggers"]
        C["Client"]:::clientStyle
        BG["Batch Test Generator"]:::clientStyle
    end

    subgraph Ingestion ["Ingestion API"]
        API["Docling Serve API<br/>FastAPI /docs"]:::apiStyle
    end

    subgraph QueueLayer ["Message Broker"]
        Redis["Redis RQ Queue<br/>rq:queue:convert"]:::queueStyle
    end

    subgraph ProcessingLayer ["Scalable Compute"]
        W1["Worker 1"]:::workerStyle
        W2["Worker 2"]:::workerStyle
        WN["Worker N"]:::workerStyle
    end

    subgraph OutputLayer ["Document Extraction"]
        DOC["Converted Output<br/>Markdown / JSON"]:::apiStyle
        LLM["Optional Pretrained LLM<br/>Structured JSON Extraction"]:::workerStyle
    end

    subgraph MLOps ["MLOps & Quality Gates"]
        DATA["Sample Docs + GT"]:::opsStyle
        EVAL["Evaluation Harness<br/>evaluate.py"]:::opsStyle
        MLFLOW["MLflow Tracking"]:::opsStyle
        GHA["GitHub Actions<br/>Quality Gate"]:::opsStyle
    end

    subgraph Platform ["Azure AKS Infrastructure"]
        TF["Terraform"]:::opsStyle
        KEDA["KEDA Scaler<br/>Redis List Scaler"]:::opsStyle
        AKS["AKS Cluster Autoscaler"]:::opsStyle
    end

    subgraph Observability ["Observability & Telemetry"]
        PROM["Prometheus Server"]:::obsStyle
        GRAF["Grafana Dashboards"]:::obsStyle
        OTEL["OpenTelemetry Tracing"]:::obsStyle
    end

    C --> API
    BG --> API
    API --> Redis
    Redis --> W1 & W2 & WN
    W1 & W2 & WN --> DOC
    DOC --> LLM
    DOC -.-> API

    TF --> Platform
    Redis -.-> KEDA
    KEDA --> WN
    Platform -.-> AKS

    DATA --> EVAL
    EVAL --> MLFLOW
    EVAL --> GHA
    GHA -.-> Platform

    API & Redis & W1 & W2 & WN -.-> PROM
    PROM --> GRAF
    API & W1 -.-> OTEL
```

### High-Level Components:
- **Docling Serve API:** FastAPI service exposing `/health`, `/v1/convert/source/async`, and `/v1/status/poll/{task_id}`.
- **Message Broker:** Redis 7 with RQ queue (`rq:queue:convert`) for asynchronous workload decoupling.
- **Worker Pool:** `docling-serve rq-worker` processes that scale independently to drain document conversion tasks.
- **MLOps Quality Gate:** Python evaluation harness (`evaluation/evaluate.py`) validating extraction accuracy against ground truth datasets (`invoice-eval-v1`) and tracking experiments in **MLflow**.
- **Autoscaling (Phases 6–8):** Kubernetes Event-driven Autoscaling (**KEDA**) scaling worker pods dynamically based on queue depth, alongside the **AKS Cluster Autoscaler**.
- **Observability (Phase 7):** Prometheus scraping queue metrics and latency percentiles, visualized in Grafana dashboards with OpenTelemetry distributed tracing.

---

## 📂 Repository Structure

```text
docling-platform/
├── .github/
│   └── workflows/
│       └── ci.yml                     # Automated CI/CD pipeline & quality gate
├── docs/
│   ├── architecture.md               # Detailed system architecture specification
│   ├── benchmark.md                  # Phase 3 worker scaling benchmark report
│   ├── opentelemetry_jaeger_setup_guide.md # Complete OpenTelemetry, Jaeger & Grafana deep-dive
│   └── runbooks/
│       ├── release_rules.md          # SRE release gating & promotion rules
│       └── rollback.md               # Disaster recovery & rollback runbook
├── evaluation/
│   ├── dataset/
│   │   └── invoice-eval-v1/          # 25 synthetic invoices + ground_truth.jsonl
│   ├── prompts/                      # Extraction prompts (baseline vs. flawed)
│   ├── reports/                      # Evaluation output reports and error diffs
│   └── evaluate.py                   # MLOps evaluator & quality gate engine
├── infra/
│   └── terraform/                    # Cloud infrastructure (Azure AKS & network)
├── k8s/                              # Kubernetes manifests & KEDA ScaledObjects
│   └── jaeger.yaml                   # Distributed tracing Jaeger All-in-One deployment
├── monitoring/                       # Prometheus alerts, Grafana dashboards & OTel
│   ├── telemetry.py                  # OpenTelemetry tracer & span context manager
│   ├── alerts.yml                    # Prometheus alerting rules
│   └── grafana/                      # Provisioned Grafana dashboards & datasources
├── reports/                          # Benchmark and failure test logs (Phases 1-3)
├── scripts/
│   ├── client.py                     # Reusable Docling API client abstraction
│   ├── smoke_test.py                 # One-command end-to-end smoke test
│   ├── submit_batch.py               # Concurrent load generator & benchmarking tool
│   └── test_worker_failure.ps1       # Fault tolerance & worker kill test
├── tests/
│   ├── unit/                         # Fast isolated unit tests (no server needed)
│   └── integration/                  # Live end-to-end API integration tests
├── docker-compose.yml                # Local Redis + API + Worker stack
├── pytest.ini                        # Pytest configuration & markers
├── pyproject.toml                    # Ruff linter & formatter configuration
└── requirements-dev.txt              # Pinned Python development dependencies
```

---

## 🚀 Quick Start (Local Docker Compose)

### 1. Start the Asynchronous Stack
```powershell
docker compose up -d
docker compose ps
```
The services are exposed and immediately accessible:
- **Docling Serve Web UI:** [http://localhost:5001/](http://localhost:5001/)
- **Docling Interactive API Docs (Swagger):** [http://localhost:5001/docs](http://localhost:5001/docs)
- **Jaeger Distributed Tracing UI:** [http://localhost:16686/](http://localhost:16686/) *(OpenTelemetry OTLP receiver on port `4318`)*
- **MLflow Experiment Tracking & Live Traces:** [http://localhost:5000/](http://localhost:5000/)
- **Grafana Operational Dashboard:** [http://localhost:3000/](http://localhost:3000/) *(Login: `admin` / `admin`)*
- **Prometheus Metrics & Alerts Engine:** [http://localhost:9090/](http://localhost:9090/)

### 2. Run the End-to-End Smoke Test
```powershell
# Set up Python virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# Run automated smoke test (logged to MLflow Traces & Jaeger)
python scripts/smoke_test.py
```

### 3. Convert Documents with OpenTelemetry & MLflow Tracing
Convert any document (online URL or local file) and automatically emit distributed OpenTelemetry traces to Jaeger and MLflow:
```powershell
# Convert a document via URL
python scripts/convert.py "https://arxiv.org/pdf/2501.17887"

# Or convert a local file and save the markdown output
python scripts/convert.py path/to/document.pdf -o output/converted.md
```
Open **[http://localhost:16686/](http://localhost:16686/)** (Jaeger UI):
- Select Service: **`docling-platform`**
- Click **"Find Traces"** to inspect the root `docling_convert` span and child spans: `submit_async_job`, `wait_for_completion`, and `get_result`.
- In MLflow at **[http://localhost:5000/](http://localhost:5000/)**, click the **"Traces"** tab to inspect the conversion span, latency breakdown, and converted markdown preview.

### 4. Run Unit and Integration Tests

```powershell
# Run fast isolated unit tests
pytest tests/unit -v

# Run live integration tests (requires running containers)
pytest tests/integration -v
```

---

## 🧪 MLOps Evaluation & Quality Gating

The platform gates releases by comparing candidate extraction prompts/models against a ground-truth dataset (`invoice-eval-v1`):

```powershell
# Evaluate baseline candidate (passes with exit code 0)
python evaluation/evaluate.py --candidate baseline --min-field-acc 0.85 --min-schema-valid 0.95

# Evaluate deliberately flawed candidate (fails with exit code 1 to block release)
python evaluation/evaluate.py --candidate flawed --min-field-acc 0.85 --min-schema-valid 0.95
```

### Inspect Runs in the MLflow UI
```powershell
mlflow server --host 127.0.0.1 --port 5000
```
Open `http://127.0.0.1:5000` to inspect experiment metrics, accuracy comparisons, and error diffs.

---

## 📊 Milestone Progress

| Phase | Description | Status | Deliverables |
|---|---|---|---|
| **Phase 1** | Local conversion baseline | ✅ Completed | One-sample sync & async conversion, latency baseline |
| **Phase 2** | Redis + RQ Worker separation | ✅ Completed | Independent worker scaling, worker failure & fault recovery |
| **Phase 3** | Automated tests & load generator | ✅ Completed | `scripts/client.py`, `submit_batch.py`, 1-worker vs 2-workers benchmark |
| **Phase 4** | MLOps evaluation & MLflow | ✅ Completed | `invoice-eval-v1` dataset, `evaluate.py`, 97% accuracy, MLflow runs |
| **Phase 5** | CI/CD & Repository Hygiene | ✅ Completed | Ruff linting, test reorganization, `.github/workflows/ci.yml`, runbooks |
| **Phase 6** | Kubernetes & Terraform | ✅ Completed (IaC & K8s) | Validated Terraform AKS modules, K8s manifests & runbooks |
| **Phase 7** | Observability & Telemetry | ✅ Completed | Prometheus scraping, Grafana dashboards, 5 alert rules, SLOs, runbooks |
| **Phase 8** | KEDA Autoscaling | ✅ Completed (Authored & Validated) | KEDA ScaledObjects (1-5 dynamic & scale-to-zero), benchmarks, runbook |
| **Phase 9** | Optional Model Serving | ⏳ Next | Pretrained LLM extraction serving evaluation |
| **Phase 10** | Portfolio Packaging | ⏳ Final | Runbooks, tear-down guides, and project walkthrough |


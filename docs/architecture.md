# System Architecture: Elastic Document Intelligence Platform

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

---

## 1. System Overview

The **Elastic Document Intelligence Platform** is an enterprise-ready, asynchronous document conversion and extraction system built with **Docling Serve**, **Redis RQ**, **Kubernetes (AKS)**, and an **MLOps evaluation and quality gating harness**.

### Key Architecture Decisions:
1. **Asynchronous Decoupling:** Ingestion API (`docling-api`) is strictly isolated from resource-intensive document conversion (`docling-worker`). Fast HTTP responses return a `task_id` within milliseconds while background workers process document hierarchies.
2. **Event-Driven Autoscaling (KEDA):** Worker scaling is driven by queue backlog length (`rq:queue:convert`) rather than lagging CPU metrics, scaling down to zero when idle.
3. **MLOps Evaluation Without Retraining:** Releases are gated by automated evaluation of schema compliance, field accuracy, and latency percentiles using MLflow tracking.

---

## 2. Core Workload Components

| Component | Technology | Role & Responsibility |
|---|---|---|
| **Ingestion API** | FastAPI / Docling Serve | Exposes OpenAPI (`/docs`), validates payloads, enqueues async jobs. |
| **Message Broker** | Redis 7 + RQ | Maintains conversion queues (`rq:queue:convert`) and job statuses. |
| **Conversion Workers** | Docling Serve RQ Worker | Consumes jobs, runs OCR & table layout parsing, outputs Markdown/JSON. |
| **Evaluation Harness** | Python + Pydantic + MLflow | Evaluates downstream field extraction against ground truth (`invoice-eval-v1`). |
| **Infrastructure** | Terraform | Provisions Azure Resource Groups, Virtual Networks, and AKS node pools. |
| **Autoscaling** | KEDA + Cluster Autoscaler | Scales worker pods based on queue length; scales VM nodes on pod demand. |
| **Observability** | Prometheus + Grafana + OTel | Scrapes queue depth, latency distributions (p50/p95), error rates, and traces. |

---

## 3. End-to-End Processing Paths

### Online Processing Path:
```text
Client / Load Generator
       │
       ▼
 Docling API (FastAPI)  ──[POST /v1/convert/source/async]──►  200 OK + task_id
       │
       ▼ Enqueue
 Redis (rq:queue:convert)
       │
       ▼ Dequeue
 Docling RQ Worker (1..N) ──► Converts Document (OCR, Tables, Hierarchy)
       │
       ▼ Store
 Converted Markdown / JSON
       │
       ▼ Optional
 Pretrained LLM ──► Structured Output (Normalized Schema)
```

### MLOps Evaluation & Quality Gating Path:
```text
 Synthetic Evaluation Dataset (invoice-eval-v1: 25 docs + ground_truth.jsonl)
       │
       ▼
 Evaluation Harness (evaluation/evaluate.py)
       │
       ├──► Logs Metrics, Parameters, and Artifacts to MLflow
       │
       ▼
 CI/CD Quality Gate (GitHub Actions)
       ├── Schema Validity >= 95%
       ├── Field Accuracy >= 85%
       └── Exact Match >= 75%
       │
   Pass: Exit Code 0 (Promote Candidate)
   Fail: Exit Code 1 (Block Release)
```


# Service Level Objectives (SLO) Specification

**Platform:** Elastic Document Intelligence Platform  
**Target Component:** Asynchronous Ingestion & Document Conversion Pipeline  
**Version:** 1.0.0 (Phase 7 Baseline)  
**Owners:** SRE / MLOps Platform Team  

---

## 1. System Context & Workload Definition

This SLO specification governs the end-to-end asynchronous document conversion pipeline:
- **Workload Type:** Standard PDF documents, synthetic invoices, and multi-page research papers (1–10 pages).
- **Processing Characteristics:** Multi-modal pipeline including document layout parsing, TableFormer structure extraction, and optical character recognition (OCR).
- **Measurement Boundary:** From HTTP `POST /v1/convert/source/async` submission until the document status becomes `success` and the converted Markdown is available at `/v1/result/{task_id}`.

---

## 2. Service Level Indicators (SLIs)

### SLI 1: Conversion Success Rate
The percentage of submitted document conversion jobs that terminate in state `success` (excluding client validation errors 4xx):

$$\text{SLI}_{\text{success}} = \frac{\text{rq\_workers\_success\_total}}{\text{rq\_workers\_success\_total} + \text{rq\_workers\_failed\_total}} \times 100\%$$

- **Measurement Tool:** Prometheus scraping `docling-api:5001/metrics`.
- **Measurement Interval:** Rolling 30-day window (evaluated in 5-minute rates).

### SLI 2: End-to-End P95 Latency
The 95th percentile duration between task submission and successful Markdown availability:

$$\text{SLI}_{\text{latency}} = \text{P95 of } (T_{\text{completed}} - T_{\text{submitted}})$$

- **Measurement Tool:** Prometheus `rq_workers_working_time_total` + client test harness metrics.
- **Measurement Interval:** Rolling 7-day window.

### SLI 3: Queue Dwell & Backlog Depth
The number of unprocessed conversion jobs waiting in Redis:

$$\text{SLI}_{\text{queue}} = \text{rq\_jobs}\{\text{queue}=\text{"convert"}, \text{status}=\text{"queued"}\}$$

- **Target:** Queue should drain to 0 between batch bursts.

---

## 3. Service Level Objectives (SLOs)

| Metric | Target (SLO) | Severe Breach (SLA Alert) | Monitored Metric |
|---|---|---|---|
| **Conversion Success Rate** | **≥ 99.0%** | < 95.0% for 5 min | `rq_workers_failed_total` rate |
| **P95 Conversion Duration** | **≤ 45.0 seconds** | > 90.0 seconds | Histogram P95 calculation |
| **Max Queue Backlog** | **≤ 5 jobs** for > 2 min | > 15 jobs for > 5 min | `rq_jobs{status="queued"}` |
| **Worker Pool Availability** | **≥ 1 idle worker** during idle periods | 0 workers registered | `sum(rq_workers)` |

---

## 4. Static Worker Baseline (Phase 3 Benchmark Evidence)

Before configuring autoscaling (Phase 8), static worker benchmarks established the following performance baselines:

| Configuration | 5-Job Wall Time | Throughput | P50 Completion | P95 Completion |
|---|---|---|---|---|
| **1 Worker Baseline** | ~78.5s | 3.82 jobs/min | 30.8s | 32.4s |
| **2 Workers Baseline** | ~47.8s | 6.28 jobs/min | 17.5s | 19.8s |

**Key Finding:** 2 workers easily satisfy the P95 $\le 45\text{s}$ SLO during concurrent batches up to 5 documents.

---

## 5. Error Budget & SRE Governance

- **Total Monthly Error Budget:** $1.0\%$ allowable failure rate ($10$ failed documents per $1,000$ submissions).
- **Budget Burn Actions:**
  - **Burn Rate > 2x:** SRE team notified; investigate worker logs via [`docs/runbooks/conversions_failing.md`](file:///c:/Users/vishal/docling-platform-local/docs/runbooks/conversions_failing.md).
  - **Burn Rate > 5x / Error Budget Exhausted:** Deployment freeze on candidate prompt / model updates until reliability returns to SLO compliance.

# Phase 3 — Baseline Performance and Worker Scaling Report

**Generated:** 2026-10-29  
**Target Workload:** 5 asynchronous document conversions (`https://arxiv.org/pdf/2501.17887`), concurrency limit = 2.  
**Test Harness:** `scripts/submit_batch.py` + `scripts/client.py`  

---

## 1. Executive Summary

In Phase 3, we built an automated, repeatable test suite and batch load generator to evaluate platform stability and quantify performance differences between worker configurations (1 worker vs. 2 workers).

- **Automated Verification:** `pytest` test suite with 11 tests (unit + live integration) passes 100%.
- **Smoke Testing:** `scripts/smoke_test.py` validates health, submission, polling, and result retrieval in a single command.
- **Worker Scaling:** Scaling from 1 worker to 2 workers reduced batch wall-clock time from **101.32s** to **95.55s**, improved median completion latency from **40.52s** to **34.43s**, and raised conversion throughput from **2.96** to **3.14** jobs/min.
- **Reliability:** 100% success rate across all submitted jobs; zero container crashes or unhandled worker errors.

---

## 2. Worker Configuration Baseline Comparison

| Metric | 1 Worker Baseline | 2 Workers Baseline | Delta / Impact |
|---|---|---|---|
| **Jobs Requested / Submitted** | 5 / 5 | 5 / 5 | Identical load |
| **Successful Completions** | 5 (100%) | 5 (100%) | No failures |
| **Failed Completions** | 0 (0%) | 0 (0%) | Zero errors |
| **Total Wall Time** | 101.32 s | 95.55 s | **-5.77 s (-5.7%)** |
| **Throughput (jobs / min)** | 2.96 | 3.14 | **+0.18 (+6.1%)** |
| **Median Completion (p50)** | 40.52 s | 34.43 s | **-6.09 s faster** |
| **95th Percentile (p95)** | 42.20 s | 44.51 s | +2.31 s (tail variability) |
| **Min Completion Latency** | 18.28 s | 20.25 s | Single job baseline |
| **Max Completion Latency** | 42.61 s | 44.99 s | Queue drain cap |
| **Final Redis Queue Depth** | 0 | 0 | Clean queue drain |
| **Worker Restarts / Crashes**| 0 | 0 | Zero instability |
| **API Memory Consumption** | ~707.7 MiB | ~655.1 MiB | Steady state |
| **Total Worker Memory** | ~1.384 GiB (1 worker) | ~2.619 GiB (2 workers) | +1.235 GiB memory footprint |

---

## 3. Analysis & Key Takeaways

1. **Independent Worker Scaling Works:**
   - Under single-worker operation, jobs serialize strictly behind the single consumer. While job 2 was picked up quickly, subsequent jobs waited in the RQ queue until the preceding document finished processing.
   - Under dual-worker operation, two jobs execute in parallel. This lowered the median turnaround time (`p50`) from 40.52s down to 34.43s.

2. **Resource Trade-offs:**
   - Each `docling-serve rq-worker` process caches document processing models in memory, consuming approximately **1.2 to 1.4 GiB** of RAM per worker.
   - For CPU-bound workloads on a local machine with shared CPU cores, scaling worker processes improves queue draining and concurrency, but CPU contention caps near-linear scaling until more hardware threads/cores or GPU accelerators are provisioned.

3. **Circuit Breaking and Fault Resistance:**
   - The batch load generator incorporates circuit-breaker logic (`--max-failures`) to avoid overloading the cluster during cascade failures.
   - The test client encapsulates schema definitions, polling deadlines, and non-terminal state handlers into `scripts/client.py`, providing a foundation for CI/CD and MLOps gates in Phases 4 & 5.

---

## 4. Artifacts Produced in Phase 3

- **Client Abstraction:** `scripts/client.py`
- **Smoke Test Runner:** `scripts/smoke_test.py`
- **Batch Load Generator:** `scripts/submit_batch.py`
- **Unit & Integration Tests:** `tests/test_unit.py`, `tests/test_integration.py`, `pytest.ini`
- **Execution Reports:**
  - `reports/phase3-smoke-test.json`
  - `reports/batch-1-worker.json`
  - `reports/batch-2-workers.json`
  - `reports/phase3-baseline-report.json`
  - `reports/phase3-baseline-report.md`


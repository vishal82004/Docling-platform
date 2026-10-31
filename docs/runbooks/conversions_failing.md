# SRE Incident Runbook: Document Conversions Failing

**Incident Severity:** P1 (Critical) if failure rate > 10%  
**Trigger Alert:** `DoclingConversionFailureRateHigh` (Prometheus)  
**Component:** Ingestion API (`docling-api`) & Worker Pipeline (`docling-worker`)  

---

## 1. Problem Description

The conversion failure rate has exceeded 5% over a 5-minute rolling window, or multiple end users report tasks finishing in state `failure`.

---

## 2. Immediate Triage & Root Cause Isolation

### Step 1: Distinguish Malformed Input from Systemic Outage
Identify whether failures are isolated to a single unparseable document or affecting all conversions:

```powershell
# 1. Check recent failure metrics in Prometheus:
curl -s http://localhost:5001/metrics | grep rq_workers_failed_total

# 2. Check failed jobs in the Redis dead-letter registry:
docker compose exec redis redis-cli ZREVRANGE rq:failed:convert 0 5
```

### Step 2: Correlate Task ID with Worker Exception Logs
Extract the `task_id` of the failed job from the API status or MLflow trace:

```powershell
# Search worker logs for the specific failed task:
docker compose logs docling-worker | Select-String -Pattern "<TASK_ID>" -Context 5, 10
```

Common root causes:
1. **Corrupt / Password-Protected PDF:** Worker logs will show `pypdf.errors.PdfReadError` or `PasswordRequired`. $\rightarrow$ User input issue, not systemic.
2. **Missing OCR Models / OCR Crash:** Worker logs show `TesseractError` or `RuntimeError: CUDA out of memory`.
3. **Redis Desynchronization:** Worker fails to report result back to Redis due to connection timeout.

---

## 3. Mitigation & Remediation Procedures

### Action A: Test Known-Good Baseline Sample
Quickly determine if the pipeline can still process standard documents:

```powershell
# Run the automated smoke test with the verified ArXiv sample:
python scripts/smoke_test.py
```

- **If Smoke Test Passes:** The failures are isolated to malformed user documents. Notify the client or return `422 Unprocessable Entity`.
- **If Smoke Test Fails:** The pipeline is broken. Proceed to Action B.

### Action B: Restart Ingestion & Worker Services
If worker Python processes are in a corrupted memory state:

```powershell
# Docker Compose:
docker compose restart docling-api docling-worker

# Kubernetes:
kubectl rollout restart deployment/docling-api deployment/docling-worker -n docling-platform
```

### Action C: Verify Redis Persistence & Memory
Confirm Redis is healthy and accessible by both API and Worker:

```powershell
docker compose exec redis redis-cli ping
# Expected output: PONG
```

---

## 4. Verification & Recovery Confirmation

1. Verify failure rate drops back to `0.0%` in Grafana:
   - Panel: *"Failed Conversions"*
2. Execute a 5-document batch load test:
   ```powershell
   python scripts/submit_batch.py --num-docs 5 --concurrency 2
   ```
   Confirm all 5 return `SUCCESS`.
3. Check MLflow Traces dashboard at `http://localhost:5000/` to ensure new conversion spans complete with status `SUCCESS`.

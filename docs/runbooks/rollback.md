# SRE / DevOps Runbook: Emergency Rollback Procedure

**Platform:** Elastic Document Intelligence Platform  
**Target Workload:** Docling Serve API & RQ Workers  

---

## 1. When to Trigger an Immediate Rollback

Trigger rollback if any of the following occur following a deployment:
- **API Error Spike:** Ingestion API error rate $> 1\%$ on `/v1/convert/source/async`.
- **Worker Crashloop:** RQ worker pods fail health checks or exit with OOMKilled status.
- **Queue Backlog Accumulation:** Redis queue depth `rq:queue:convert` grows continuously without draining.
- **Data Quality Regression:** Downstream extraction parser error rate exceeds $5\%$.

---

## 2. Local Docker Compose Rollback

### Step 1: Drain or Preserve Active Queue
```powershell
# Check current queue length
docker compose exec redis redis-cli LLEN rq:queue:convert
```

### Step 2: Roll Back to Last Known-Good Version / Tag
```powershell
# Revert working directory to last known-good release commit
git checkout <last-known-good-tag-or-sha>

# Re-deploy the containers cleanly
docker compose up -d --remove-orphans
docker compose ps
```

### Step 3: Verify Service Health & Queue Draining
```powershell
# Verify API health
curl http://127.0.0.1:5001/health

# Run smoke test suite
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

---

## 3. Kubernetes (AKS) Rollback (Preview for Phase 6)

```powershell
# 1. Roll back deployment to previous revision
kubectl rollout undo deployment/docling-worker -n docling-platform
kubectl rollout undo deployment/docling-api -n docling-platform

# 2. Check rollout status
kubectl rollout status deployment/docling-worker -n docling-platform
kubectl rollout status deployment/docling-api -n docling-platform

# 3. Verify pod status
kubectl get pods -n docling-platform -l app=docling-worker
```

---

## 4. Post-Incident Review
1. Export logs from failed worker/API containers before pruning:
   ```powershell
   docker compose logs --tail 500 docling-worker > reports/failed-worker.log
   ```
2. Archive MLflow evaluation run details and note root cause in post-mortem documentation.

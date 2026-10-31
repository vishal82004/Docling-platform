# SRE Incident Runbook: Queue Backlog Rising

**Incident Severity:** P2 (High) / P1 if Backlog > 20 jobs  
**Trigger Alert:** `DoclingQueueBacklogHigh` (Prometheus)  
**Component:** Message Broker (`redis`) & Worker Pool (`docling-worker`)  

---

## 1. Problem Description

The number of unconsumed document conversion tasks in the Redis queue (`rq:queue:convert`) has exceeded the threshold (> 5 jobs) for more than 1 minute. End users may experience delayed task completion or timeout errors.

---

## 2. Immediate Triage & Diagnostics

### Step 1: Confirm Queue Backlog & Growth Rate
Run Redis CLI inspection to verify current queue length:

```powershell
# For Docker Compose:
docker compose exec redis redis-cli LLEN rq:queue:convert

# For Kubernetes:
kubectl exec -n docling-platform deploy/redis -- redis-cli LLEN rq:queue:convert
```

### Step 2: Check Worker Health & Registration Status
Verify that worker processes are actually registered and consuming from the queue:

```powershell
# In Docker Compose:
docker compose ps docling-worker

# Check how many workers Prometheus detects:
curl -s http://localhost:5001/metrics | grep rq_workers
```

If `sum(rq_workers)` is 0 or less than expected:
- The worker process has crashed or lost connectivity to Redis.
- Check worker logs: `docker compose logs docling-worker --tail 50`.

### Step 3: Inspect Worker Logs for OOM or Hanging Tasks
Check if workers are hanging on a huge document or crashed due to Out-Of-Memory (OOM):

```powershell
# Inspect container exit codes and restarts:
docker inspect docling-platform-local-docling-worker-1 --format '{{.State.Status}} (OOMKilled: {{.State.OOMKilled}})'
```

---

## 3. Mitigation & Remediation Procedures

### Action A: Scale Worker Capacity Manually

If workers are healthy but overwhelmed by a sudden traffic burst:

```powershell
# Scale to 4 workers in Docker Compose:
docker compose up -d --scale docling-worker=4

# Or in Kubernetes:
kubectl scale deployment docling-worker -n docling-platform --replicas=4
```

### Action B: Restart Stuck Workers
If a worker process is hung indefinitely on an unprocessable document:

```powershell
# In Docker Compose:
docker compose restart docling-worker

# In Kubernetes:
kubectl rollout restart deployment/docling-worker -n docling-platform
```

### Action C: Inspect Redis Resource Limits
Confirm Redis is not running out of memory or dropping commands:

```powershell
docker compose exec redis redis-cli INFO memory
docker compose exec redis redis-cli INFO stats
```

---

## 4. Verification & Recovery Confirmation

1. Monitor the queue draining in Grafana: **[http://localhost:3000/](http://localhost:3000/)** -> Panel *"Queue Backlog (Waiting)"*.
2. Verify queue depth drops back to `0`:
   ```powershell
   docker compose exec redis redis-cli LLEN rq:queue:convert
   ```
3. Run the automated smoke test to verify end-to-end processing has resumed:
   ```powershell
   python scripts/smoke_test.py
   ```
4. Record the root cause (traffic spike, worker crash, or stuck document) in the post-mortem log.

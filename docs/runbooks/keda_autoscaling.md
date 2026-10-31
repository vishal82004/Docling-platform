# SRE / DevOps Runbook: KEDA Autoscaler Operations

**Platform:** Elastic Document Intelligence Platform  
**Target:** Event-Driven Worker Autoscaling (`docling-worker-scaler`)  
**Scope:** Kubernetes & AKS Environments  

---

## 1. Prerequisites Checklist

Before deploying the KEDA ScaledObject:
- [ ] KEDA operator installed on cluster:
  ```powershell
  # Check if KEDA is installed:
  kubectl get pods -n keda
  ```
  If not installed:
  ```powershell
  helm repo add kedacore https://kedacore.github.io/charts
  helm repo update
  helm install keda kedacore/keda --namespace keda --create-namespace
  ```
- [ ] Worker Deployment `docling-worker` is running in `docling-platform`.
- [ ] Redis service is reachable at `redis.docling-platform.svc.cluster.local:6379`.

---

## 2. Deploying & Verifying the ScaledObject

### Step 1: Apply the ScaledObject
```powershell
kubectl apply -f k8s/keda-scaledobject.yaml
```

### Step 2: Verify KEDA Registration
```powershell
kubectl get scaledobject -n docling-platform
```
**Expected Output:**
```text
NAME                    SCALETARGETKIND      SCALETARGETNAME   MIN   MAX   TRIGGERS   AUTHENTICATION   READY   ACTIVE   AGE
docling-worker-scaler   apps/v1.Deployment   docling-worker    1     5     redis                       True    False    30s
```
- `READY = True`: KEDA successfully connected to Redis and validated the configuration.
- `ACTIVE = False`: Currently 0 jobs in queue (worker idling at min 1 replica).
- When jobs are queued, `ACTIVE` immediately flips to `True`!

### Step 3: Inspect the Generated HPA
KEDA automatically generates and manages an underlying Kubernetes HorizontalPodAutoscaler:
```powershell
kubectl get hpa -n docling-platform
```

---

## 3. Simulating Queue Load & Verifying Scale-Out

To test KEDA autoscaling under live load:

```powershell
# 1. In Terminal 1, watch worker pods:
kubectl get pods -n docling-platform -l app.kubernetes.io/name=docling-worker -w

# 2. In Terminal 2, submit a concurrent batch of 10 jobs:
python scripts/submit_batch.py --num-docs 10 --concurrency 4

# 3. Observe:
#   - Queue backlog rises > 2
#   - KEDA triggers scale-up from 1 -> 3 -> 5 pods
#   - All 10 jobs drain in parallel
#   - After 60s cooldown, pods scale back down to 1
```

---

## 4. Troubleshooting Common Failures

### Issue 1: ScaledObject reports `READY = False`
- **Symptom:** `kubectl describe scaledobject docling-worker-scaler -n docling-platform` shows `error connecting to Redis`.
- **Root Cause:** Incorrect Redis DNS address or port.
- **Fix:** Verify internal connectivity:
  ```powershell
  kubectl run test-redis --rm -it --image=redis:7-alpine -n docling-platform -- redis-cli -h redis.docling-platform.svc.cluster.local ping
  ```

### Issue 2: Workers do not scale up when jobs arrive
- **Symptom:** `ACTIVE = False` even when jobs are queued in Redis.
- **Root Cause:** Wrong `listName` in the trigger.
- **Fix:** Confirm actual queue key in Redis matches the trigger:
  ```powershell
  kubectl exec -n docling-platform deploy/redis -- redis-cli SMEMBERS rq:queues
  # Must match: rq:queue:convert
  ```

### Issue 3: Pod Flapping (Rapid Scale-Up and Scale-Down)
- **Symptom:** Pods terminate before completing tasks or keep bouncing between 1 and 3 replicas.
- **Fix:** Increase the cooldown period in `k8s/keda-scaledobject.yaml`:
  ```yaml
  cooldownPeriod: 120 # Increase from 60 to 120 seconds
  ```

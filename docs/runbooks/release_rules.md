# SRE / DevOps Runbook: Release Rules & Quality Gating

**Platform:** Elastic Document Intelligence Platform  
**Target Environment:** Local Docker Compose / Azure Kubernetes Service (AKS)  
**Classification:** DevOps / SRE Operations Policy  

---

## 1. Automated Release Gating Policy

No code, prompt, model artifact, container image, or Kubernetes manifest may be deployed to production without passing all automated CI/CD gates.

```text
+-----------------------+     +-----------------------+     +-----------------------+
|  1. Linter & Format   | --> |   2. Fast Unit Tests  | --> | 3. Compose Validation |
|  Ruff Check & Format  |     |   pytest tests/unit   |     | docker compose config |
+-----------------------+     +-----------------------+     +-----------------------+
                                                                        |
                                                                        v
+-----------------------+     +-----------------------+     +-----------------------+
|  6. Immutable Release | <-- |  5. Infrastructure    | <-- | 4. MLOps Quality Gate |
|  Git Tag / Git SHA    |     |  terraform validate   |     | evaluate.py (97% Acc) |
+-----------------------+     +-----------------------+     +-----------------------+
```

### Thresholds Required to Pass:
| Gate | Metric | Required Threshold | Action on Breach |
|---|---|---|---|
| **Unit Tests** | Passing rate | $100\%$ | Pipeline stops immediately. |
| **Linting & Code Quality** | Ruff errors | $0$ errors | Commit rejected. |
| **Schema Conformance** | `schema_valid_rate` | $\ge 95.0\%$ | Release blocked; exit code `1`. |
| **Extraction Accuracy** | `overall_field_accuracy` | $\ge 85.0\%$ | Release blocked; exit code `1`. |
| **Exact Match Rate** | `exact_match_rate` | $\ge 75.0\%$ | Release blocked; exit code `1`. |
| **Pipeline Latency** | `p95_latency_sec` | $\le 5.0$ s | Flagged for latency regression. |
| **Unhandled Errors** | `failure_rate` | $\le 5.0\%$ | Release blocked; exit code `1`. |

---

## 2. Container Image & Artifact Immutability

1. **No Mutable Tags in Production:**
   - Using `:latest` tag for Docling API, workers, or custom images in production manifests is strictly prohibited.
   - All deployments must pin explicit digests or immutable semantic version tags (e.g. `quay.io/docling-project/docling-serve:v2.1.0` or git commit SHA `sha-4a9b2d8`).
2. **Configuration Freezes:**
   - Worker configurations (concurrency, queue names, memory limits) must be version-controlled in git and verified through staging benchmarks before merging.

---

## 3. Pre-Promotion Verification Checklist

Before promoting a candidate configuration from evaluation to production:
- [ ] Automated CI workflow passes on the pull request.
- [ ] MLflow experiment run shows zero accuracy regression compared to the baseline run.
- [ ] Docker compose configuration validates without warnings (`docker compose config`).
- [ ] No private datasets, API keys, credentials, or `.env` files are tracked in git.
- [ ] Last known-good rollback target is documented and available.


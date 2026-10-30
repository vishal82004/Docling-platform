# Elastic Document Intelligence Platform
## Step-by-step implementation guide

**Starting point:** You previously started Docling Serve locally. This guide now includes the commands to reset the local test container and start again from the beginning. It proceeds from local tests to Azure only after the local processing path works.

**Goal:** Build a portfolio-ready document-processing platform that demonstrates asynchronous processing, reliability engineering, MLOps evaluation, CI/CD, Kubernetes, queue-based autoscaling, observability, and cost awareness.

**Important:** We do not need to train a model from scratch. We'll begin with Docling conversion. A separate pretrained LLM for extracting fields (for example, from invoices) is an optional extension and should only be added if it gives measurable value.

---

# 1. Architecture first

## 1.1 Target architecture

```text
ONLINE PROCESSING PATH
======================
Client / batch test generator
          |
          v
    Docling Serve API
          |
          v
     Redis + RQ queue
      (convert queue)
          |
          v
    Docling RQ workers
          |
          v
  Converted Markdown / JSON
          |
          +------------------------------+
          |                              |
          v                              v
 Return/store conversion         OPTIONAL pretrained LLM
 output + task status            extracts defined fields
                                        |
                                        v
                                  Structured JSON

MLOPS / RELEASE PATH
===================
Sample documents + expected JSON
          |
          v
Python evaluation harness -------> MLflow Tracking
          |                          params, metrics,
          |                          reports, failures
          v
GitHub Actions quality gate
          |
      pass / fail
          |
          v
Approved configuration is eligible for deployment

PLATFORM / OPERATIONS PATH
==========================
Terraform -> Azure resources / AKS
                    |
                    +-- Docling API Deployment + Service
                    +-- Redis
                    +-- Docling RQ worker Deployment
                    +-- optional model inference service
                    +-- KEDA -> worker pod replicas
                    +-- AKS Cluster Autoscaler -> node count
                    +-- Prometheus / Grafana
                    +-- OpenTelemetry instrumentation, where supported

GitHub Actions -> tests / evaluation / manifest checks / deployment
```

## 1.2 Responsibility of each component

| Component | Why we use it |
|---|---|
| Docling Serve | Converts documents into structured content |
| Redis + RQ | Queues work so the API and conversion workers can scale independently |
| Python test client | Repeats requests and measures latency and outcomes |
| Optional pretrained LLM | Extracts a defined JSON schema from converted text, if worthwhile |
| Evaluation harness | Compares outputs with ground-truth answers |
| MLflow | Records evaluation runs, configuration, metrics, and artifacts; it does not train the model |
| GitHub Actions | Runs tests and blocks promotion if required checks fail |
| Terraform | Creates reproducible Azure infrastructure |
| AKS | Runs API and worker workloads on Kubernetes |
| KEDA | Scales worker pod replicas from queue demand |
| AKS Cluster Autoscaler | Adds/removes eligible nodes based on pod scheduling demand |
| Prometheus + Grafana | Makes throughput, errors, queue health, latency, and resource use visible |
| OpenTelemetry | Traces requests across components when instrumentation is available |

### Important architecture decisions

1. **Docling already performs document AI conversion.** Do not add an LLM just to increase the tool count.
2. **MLOps here does not require training.** We will evaluate pretrained model/configuration versions, gate releases, and monitor serving behavior.
3. **Use Docling's RQ engine for independently scalable workers.** Its default local engine runs jobs in the API process; RQ uses Redis and separate `docling-serve rq-worker` processes. See the [official deployment guide](https://docling-project.github.io/docling/usage/api_server/deployment/).
4. **Verify the queue key before configuring KEDA.** RQ's default queue commonly appears as `rq:queue:convert`, but inspect the actual key in your environment. KEDA's Redis Lists scaler works with the length of a Redis list: [documentation](https://keda.sh/docs/latest/scalers/redis-lists/).
5. **Scaling a pod to zero does not shut down a GPU VM automatically.** GPU node autoscaling is a separate concern. We will start CPU-only.
6. **Keep Redis private.** Do not publish its port to the Internet. Use secrets for credentials in cloud deployments.
7. **Follow the OpenAPI schema exposed by your running `http://localhost:5001/docs`.** Request payloads can vary with Docling Serve API/image versions. If an example below differs from your actual schema, use the schema shown by the running container.

---

# 2. Milestones

| Phase | Outcome | Completion test |
|---|---|---|
| 1 | Local conversion baseline | One sample converts; request and timing are recorded |
| 2 | Redis + RQ | API queues a job and separate worker completes it |
| 3 | Automated tests and load generator | Batch report compares worker counts and failure cases |
| 4 | MLOps evaluation | Labelled dataset, evaluation reports, and MLflow runs exist |
| 5 | CI/CD | Tests run on pushes/PRs and failing checks block release |
| 6 | Kubernetes + Terraform | CPU deployment can be recreated from code |
| 7 | Observability | Dashboards show queue health, latency, errors, and replicas |
| 8 | KEDA | Worker replicas scale with queue backlog and safely scale in |
| 9 | Optional model serving | KServe/vLLM/GPU added only if benchmark and budget justify it |
| 10 | Portfolio packaging | Diagram, benchmark, runbooks, setup and teardown guide are documented |

---

# Phase 0 — Fresh local workspace and Docker checks

Run these steps in **PowerShell** on Windows 11. Docker Desktop must be open and running.

## Step 0.1 — Verify Docker and Compose

```powershell
docker version
docker compose version
```

Both commands should return version/details without a daemon connection error. If Docker cannot connect to the daemon, start Docker Desktop and retry.

## Step 0.2 — Remove the previous one-container test

This removes only the container named `docling-serve`, if it exists. It does not delete the image or other containers.

```powershell
$existing = docker ps -aq --filter "name=^/docling-serve$"
if ($existing) {
    docker rm -f docling-serve
}
```

If you previously ran a Compose stack from this project and intentionally want to stop it, navigate to that stack's folder and run `docker compose down`. Avoid `docker compose down -v` unless you intentionally want to delete its named volumes and their data.

## Step 0.3 — Create and enter the project folder

```powershell
$ProjectRoot = Join-Path $HOME "docling-platform-local"
New-Item -ItemType Directory -Force -Path $ProjectRoot | Out-Null
Set-Location $ProjectRoot

New-Item -ItemType Directory -Force -Path `
  "reports", "scripts", "tests", "docs", "samples", "evaluation", "k8s", "monitoring", "infra" | Out-Null

Get-Location
```

Run later commands from this project folder unless the step explicitly tells you to change directories. If you already have a repository with work you want to preserve, use that directory instead of creating another copy.

---

# Phase 1 — Verify local Docling conversion

Phase 0 removed the old named container if it existed. Start the CPU container again for a fresh test.

## Step 1.1 — Start Docling Serve and inspect logs

```powershell
docker run -d `
  --name docling-serve `
  -p 127.0.0.1:5001:5001 `
  -e DOCLING_SERVE_ENABLE_UI=1 `
  quay.io/docling-project/docling-serve
```

Then inspect the container and logs:

```powershell
docker ps --filter "name=docling-serve"
docker logs --tail 100 docling-serve
```

If it is not running, inspect its exit state:

```powershell
docker ps -a --filter "name=docling-serve"
```

## Step 1.2 — Check health and API docs

```powershell
Invoke-RestMethod -Uri "http://localhost:5001/health"
```

Open `http://localhost:5001/docs`, `http://localhost:5001/ui`, and `http://localhost:5001/health` in your browser. In `/docs`, locate the source-conversion endpoint and inspect its request schema.

## Step 1.3 — Convert one small sample

Use **Try it out** in `/docs` first. A sample URL used in official Docling Serve documentation is `https://arxiv.org/pdf/2501.17887`.

The current official usage guide documents `http_sources: [{url: ...}]` for URL input. Use `/docs` to check whether your running image exposes this same schema:

```powershell
$BaseUrl = "http://127.0.0.1:5001"
$body = @{
  http_sources = @(
    @{ url = "https://arxiv.org/pdf/2501.17887" }
  )
  options = @{
    to_formats = @("md")
  }
} | ConvertTo-Json -Depth 10

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$response = Invoke-RestMethod `
  -Uri "$BaseUrl/v1/convert/source" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body `
  -TimeoutSec 600
$stopwatch.Stop()

$response | ConvertTo-Json -Depth 100 | Set-Content -Encoding utf8 ".\reports\phase1-sync-result.json"
Write-Host "Conversion finished in $([math]::Round($stopwatch.Elapsed.TotalSeconds, 2)) seconds."
$response | ConvertTo-Json -Depth 5
```

If your local `/docs` schema differs, use the actual schema instead of repeatedly trying this payload.

## Step 1.4 — Record the baseline

Record document type/page count, wall-clock duration, whether conversion succeeded, whether text/tables look correct, and any warnings in the container logs. Do not use confidential documents in the public demo.

## Step 1.5 — Save the baseline artifacts

Phase 0 already created the workspace. Save the successful request, a sanitized response, and the measured duration under `reports/`. The synchronous test above writes `reports\phase1-sync-result.json`.

If you opened a new PowerShell window, return to the project root before running relative-path commands:

```powershell
$ProjectRoot = Join-Path $HOME "docling-platform-local"
Set-Location $ProjectRoot
Get-ChildItem
```

**Phase 1 is complete when:** one document converts successfully; you understand the endpoint and response; you have a recorded baseline.

---

# Phase 2 — Move to Redis + RQ workers

## Goal

Separate API request handling from the expensive conversion work. This is the foundation for independent worker scaling.

## Step 2.1 — Stop the original test container

After you have the Phase 1 result:

```powershell
docker stop docling-serve
```

## Step 2.2 — Create `docker-compose.yml`

Create the file below in the project root:

```yaml
services:
  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped

  docling-api:
    image: quay.io/docling-project/docling-serve
    entrypoint: ["docling-serve"]
    command: ["run"]
    environment:
      DOCLING_SERVE_ENABLE_UI: "1"
      DOCLING_SERVE_ENG_KIND: "rq"
      DOCLING_SERVE_ENG_RQ_REDIS_URL: "redis://redis:6379/0"
      DOCLING_SERVE_ENG_RQ_QUEUE_NAME: "convert"
    ports:
      - "127.0.0.1:5001:5001"
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped

  docling-worker:
    image: quay.io/docling-project/docling-serve
    entrypoint: ["docling-serve"]
    command: ["rq-worker"]
    environment:
      DOCLING_SERVE_ENG_KIND: "rq"
      DOCLING_SERVE_ENG_RQ_REDIS_URL: "redis://redis:6379/0"
      DOCLING_SERVE_ENG_RQ_QUEUE_NAME: "convert"
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped

volumes:
  redis-data:
```

This is a local-development configuration. Once working, pin the same exact Docling image version/digest for API and worker rather than relying on a mutable default tag. For production, use authenticated secret-managed Redis access and appropriate TLS/network controls. Redis is intentionally not published on the host in this example.

## Step 2.3 — Start and inspect the stack

```powershell
docker compose up -d
docker compose ps
docker compose logs --tail 100 docling-api
docker compose logs --tail 100 docling-worker
```

Reopen `http://localhost:5001/docs`.

## Step 2.4 — Submit an async job using PowerShell

First confirm the current request schema in `http://localhost:5001/docs`. The current official usage documentation shows `http_sources` for URL input; use the schema exposed by your running server if it differs. Official endpoint sequence: `POST /v1/convert/source/async`, `GET /v1/status/poll/{task_id}`, and `GET /v1/result/{task_id}`.

```powershell
$BaseUrl = "http://127.0.0.1:5001"
$body = @{
  http_sources = @(
    @{ url = "https://arxiv.org/pdf/2501.17887" }
  )
  options = @{
    to_formats = @("md")
  }
} | ConvertTo-Json -Depth 10

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$task = Invoke-RestMethod `
  -Uri "$BaseUrl/v1/convert/source/async" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body `
  -TimeoutSec 60

$task | Format-List *
$taskId = $task.task_id
if (-not $taskId) { throw "No task_id returned. Inspect the response and API logs." }
Write-Host "Task ID: $taskId"

$deadline = (Get-Date).AddMinutes(10)
$status = $task
do {
  Start-Sleep -Seconds 3
  $status = Invoke-RestMethod `
    -Uri "$BaseUrl/v1/status/poll/$taskId" `
    -Method Get `
    -TimeoutSec 30
  Write-Host "Status: $($status.task_status)"
} while (
  $status.task_status -notin @("success", "failure") -and
  (Get-Date) -lt $deadline
)
$stopwatch.Stop()

$status | Format-List *
Write-Host "End-to-end elapsed seconds: $([math]::Round($stopwatch.Elapsed.TotalSeconds, 2))"

if ($status.task_status -eq "success") {
  $result = Invoke-RestMethod `
    -Uri "$BaseUrl/v1/result/$taskId" `
    -Method Get `
    -TimeoutSec 120
  $result | ConvertTo-Json -Depth 100 |
    Set-Content -Encoding utf8 ".\reports\phase2-async-result.json"
  Write-Host "Saved result to reports\phase2-async-result.json"
} else {
  Write-Warning "Task did not succeed before the deadline. Inspect task status and worker logs."
}
```

If the job stays queued indefinitely, inspect worker logs and Redis connection settings first. API and worker must use the same `DOCLING_SERVE_ENG_RQ_REDIS_URL`, and at least one worker must be running. If the response schema or route differs, follow your running `/docs` page rather than assuming a different version's schema.

## Step 2.5 — Inspect the queue and submit a small batch

```powershell
docker compose exec redis redis-cli --scan --pattern "rq:queue:*"
docker compose exec redis redis-cli LLEN rq:queue:convert
```

The queue can empty too quickly to observe. Submit five jobs at once, or temporarily stop workers to see backlog form. Do not clear the queue unless you intend to delete pending work.

```powershell
$BaseUrl = "http://127.0.0.1:5001"

$body = @{
    sources = @(
        @{
            kind = "http"
            url  = "https://arxiv.org/pdf/2501.17887"
        }
    )
    options = @{
        to_formats = @("md")
    }
} | ConvertTo-Json -Depth 10

$tasks = @()

1..5 | ForEach-Object {

    $task = Invoke-RestMethod `
        -Uri "$BaseUrl/v1/convert/source/async" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body `
        -TimeoutSec 60

    $tasks += $task

    Write-Host "Submitted job $_ : $($task.task_id)"
}

$tasks | Format-Table task_id, task_status, task_position
```

Check the queue again while jobs are pending:

```powershell
docker compose exec redis redis-cli LLEN rq:queue:convert
```

## Step 2.6 — Add a second worker

```powershell
docker compose up -d --scale docling-worker=2
docker compose ps
```

Submit the same small batch with one worker and two workers; compare completion time, throughput, CPU and memory. Do not assume adding a worker improves performance until the measurements show it.

## Step 2.7 — Test worker failure

1. Queue several jobs.
2. Stop one worker while work is pending.
3. Check API availability and job statuses.
4. Start the worker again.
5. Observe whether queued/active jobs complete, retry, or fail.
6. Document actual behavior and any lost/failed work.

**Phase 2 is complete when:** API, Redis, and workers are separate; async jobs reach a terminal status; two workers can consume jobs; worker restart behavior is documented.

---

# Phase 3 — Build repeatable tests and a load generator

## Step 3.1 — Create a Python environment

From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install requests pytest
pip freeze > requirements-dev.txt
```

If virtual-environment activation is blocked by local PowerShell policy, follow your environment's policy or use `.venv\Scripts\python.exe` directly.

## Step 3.2 — Write `scripts/smoke_test.py`

The script should:

1. call the health endpoint;
2. submit a test conversion using the schema verified in Phase 1;
3. capture the task ID if using async mode;
4. poll until terminal status or timeout;
5. write timestamps, outcome, and elapsed seconds to JSON;
6. exit with a non-zero status if the test fails.

Keep endpoint paths and request payload construction in one place so API-version adjustments are easy.

## Step 3.3 — Add tests

Create separate unit and integration tests for:

- health endpoint success;
- submission of a known-good sample;
- malformed request/invalid URL returns a controlled error;
- status polling handles a non-terminal state;
- polling stops at a timeout instead of looping forever;
- a failed task is not counted as successful.

Unit tests should run without the Docling service; integration tests may require a running service.

## Step 3.4 — Create `scripts/submit_batch.py`

The batch tool should accept a job count and concurrency limit, submit a known set of non-sensitive sample documents, record each task ID and outcome, measure queue wait/total completion where observable, and stop after repeated failures. Start with 5, then 10, then 20 jobs—do not start with a huge burst.

## Step 3.5 — Record a baseline table

For one worker and two workers, measure:

- jobs submitted/completed/failed;
- jobs per minute;
- p50/p95 completion time where the sample count supports it;
- queue depth and oldest-job age if available;
- CPU/memory use;
- worker restarts and errors.

**Phase 3 is complete when:** one command performs a smoke test, batch runs produce reports, and you can explain differences between worker configurations.

---

# Phase 4 — Add MLOps evaluation and MLflow

## Goal

Track how well a pretrained model/configuration performs, without training a model from scratch.

There are two scopes:

- **Document-conversion-only:** label examples and measure conversion success, relevant table/text extraction quality, and latency.
- **Recommended MLOps extension:** after Docling converts a document, call a separate pretrained model to extract a fixed JSON schema such as invoice number, vendor, date, and total. Evaluate that model's outputs against ground truth.

Only add the LLM stage if you can define its task and show its value. It remains separate from Docling's conversion stage.

## Step 4.1 — Define the output schema

For invoice extraction, a sample expected output might look like:

```json
{
  "invoice_number": "INV-001",
  "vendor": "Example Supplies",
  "invoice_date": "2026-01-15",
  "total": 1250.50
}
```

Define field types and normalization first: ISO dates, numeric totals, currency/tolerance rules, and how missing values are represented.

## Step 4.2 — Create a labelled dataset

- Start with approximately 20–50 synthetic or appropriately licensed documents.
- Include different layouts, missing fields, tables, and a few difficult cases.
- Store expected JSON answers alongside the documents.
- Keep the dataset for evaluation; this is not training data in this project.
- Do not commit private documents or personal data.
- Give it a version such as `invoice-eval-v1`.

Suggested layout:

```text
evaluation/
  dataset/invoice-eval-v1/
    documents/
    ground_truth.jsonl
  prompts/extraction-v1.txt
  evaluate.py
  reports/
```

## Step 4.3 — Choose and pin a pretrained endpoint

Start with a model that can run locally or through a suitable endpoint within your budget; GPU/Kubernetes is not required yet. Pin the model ID/revision if available, prompt version, decoding settings, schema version, and dataset version. Parse and validate JSON strictly; invalid schema should count as a failed output.

## Step 4.4 — Write `evaluation/evaluate.py`

For each document:

1. call Docling and capture converted text;
2. call the pretrained LLM only if the extraction extension is enabled;
3. parse output JSON and validate required fields/types;
4. compare each field against ground truth using the normalization rules;
5. record field-level correctness, whole-record correctness, schema validity, exceptions, and latency;
6. save aggregate metrics to `report.json` and detailed error examples separately.

Use relevant metrics: field-level accuracy, whole-record exact-match rate, valid JSON/schema rate, missing-field rate, request-failure rate, p50/p95 latency. Document each metric's calculation. Do not call a metric "model accuracy" if it only measures API success.

## Step 4.5 — Track runs in MLflow

```powershell
pip install mlflow
pip freeze > requirements-dev.txt
```

Integrate MLflow Tracking into the evaluator. Each evaluation run should log:

**Parameters:** model ID/revision, prompt version, decoding settings, dataset version, code commit if available.  
**Metrics:** field-level accuracy, exact-match rate, schema-validity rate, failure rate, latency.  
**Artifacts:** aggregate report, error examples, and benchmark CSV.

Example structure to integrate with your real evaluation variables:

```python
import mlflow

with mlflow.start_run():
    mlflow.log_param("dataset_version", "invoice-eval-v1")
    mlflow.log_param("prompt_version", "extraction-v1")
    mlflow.log_metric("field_accuracy", field_accuracy)
    mlflow.log_metric("schema_valid_rate", schema_valid_rate)
    mlflow.log_metric("p95_latency_seconds", p95_latency_seconds)
    mlflow.log_artifact("evaluation/reports/report.json")
```

## Step 4.6 — Compare two candidates

Use the same dataset for both candidates. Candidate differences might be a second pretrained model, a changed prompt, or a configuration. Avoid changing model, prompt, and data version at the same time, because you won't know what caused the result to change.

## Step 4.7 — Enforce quality thresholds

Choose thresholds before evaluating the final candidate. For example, require a minimum schema-valid rate, field accuracy not below the known-good baseline, bounded failure rate, and latency under a chosen target. These values must be justified by your dataset/use case.

Make `evaluate.py` exit with code `1` if any required gate fails. Keep a known-good configuration for rollback.

## Step 4.8 — Run the MLflow UI locally

```powershell
mlflow server --host 127.0.0.1 --port 5000
```

Open `http://127.0.0.1:5000`. Configure your evaluator to log to the local tracking server as supported by the installed MLflow version. Keep the setup local initially; persistent databases/remote artifact storage are later enhancements.

**Phase 4 is complete when:** a labelled dataset exists, the evaluator is reproducible, at least two runs are visible in MLflow, and a deliberately bad candidate fails the gate.

---

# Phase 5 — CI/CD and repository hygiene

## Step 5.1 — Organize the repo

```text
docling-platform/
  README.md
  docker-compose.yml
  requirements-dev.txt
  scripts/
  tests/unit/
  tests/integration/
  evaluation/
  infra/terraform/
  k8s/
  monitoring/
  docs/architecture.md
  docs/benchmark.md
  docs/runbooks/
```

Add a `.gitignore` for `.venv/`, `.env`, secrets, local model caches/weights, temporary outputs, local MLflow data if not publishing it, and private documents.

## Step 5.2 — Add code checks

Use a linter/formatter such as Ruff and unit tests with pytest. Keep tests requiring a live Docling service marked as integration tests. Keep CI inputs small, deterministic, and non-sensitive.

## Step 5.3 — Create GitHub Actions workflow

On push and pull request:

1. checkout code;
2. setup Python;
3. install development dependencies;
4. run format/lint checks;
5. run unit tests;
6. validate the Compose configuration;
7. run `terraform fmt -check` and `terraform validate` when infrastructure code changes;
8. run evaluation/quality-gate tests when model/prompt/evaluation code changes, using a controlled endpoint or deterministic fixture;
9. upload evaluation/test reports as workflow artifacts.

Do not require a costly or unreliable GPU endpoint for every pull request. Keep most CI fast; run full inference/load tests in a controlled job.

## Step 5.4 — Define release rules

- Test failure blocks deployment.
- Evaluation threshold failure blocks candidate promotion.
- Use immutable commit SHAs/version tags for images and deployment configuration.
- Document rollback to the last known-good version.

## Step 5.5 — Add ACR only when needed

The official Docling image can be referenced directly at first. Azure Container Registry makes sense when you have a project-owned gateway, exporter, or custom image to publish; don't create it merely to add another logo to the architecture.

**Phase 5 is complete when:** CI runs on push/PR, failed checks block release, and no secrets/private documents are committed.

---

# Phase 6 — Kubernetes deployment with Terraform

## Step 6.1 — Pick a low-cost first cluster

If local Kubernetes is stable, validate manifests locally first. Otherwise, create a temporary CPU-only AKS cluster for a short window. Do not start with GPU nodes. Check current regional availability, quota and pricing before applying resources. Set budget alerts if available and destroy temporary resources when finished.

## Step 6.2 — Write Terraform configuration

Under `infra/terraform/`, declare only what is needed for the first deployment:

- resource group;
- AKS cluster with a small CPU node pool;
- optional ACR if you have your own image;
- necessary identities/permissions;
- outputs for cluster name and resource group.

Use variables for location, resource names, node count and sizing. Never put credentials in `.tf` files. Follow current AzureRM provider docs.

## Step 6.3 — Review the plan before applying

From `infra/terraform/`:

```powershell
terraform fmt -recursive
terraform init
terraform validate
terraform plan
```

Read the plan and verify region, VM size, node count and resource list. Then, only when it matches expectations:

```powershell
terraform apply
```

## Step 6.4 — Connect to AKS

First verify the Azure CLI, Terraform and kubectl are installed:

```powershell
az version
terraform version
kubectl version --client
```

Then sign in and confirm the active subscription **before** creating resources:

```powershell
az login
az account show
az account list --output table
```

Use the intended subscription in the Azure portal/CLI, then retrieve cluster credentials and verify connectivity:

```powershell
az aks get-credentials --resource-group <resource-group> --name <cluster-name>
kubectl get nodes
kubectl get namespaces
```

Replace placeholders with Terraform outputs. Verify `kubectl` is pointing at the cluster you intend to use.

## Step 6.5 — Create Kubernetes resources

Create manifests (or Helm values) for Redis, the Docling API Deployment/Service, and the Docling RQ worker Deployment. Include resource requests/limits, supported health probes, required ConfigMaps/Secrets, and a ClusterIP-only Redis service. Expose the API only through a controlled test route/port-forward.

Use the same Docling image version for API and workers. The [official deployment examples](https://github.com/docling-project/docling-serve/tree/main/docs/deploy-examples) are a reference, not a substitute for reviewing the manifest. Do not copy sample passwords into the project.

## Step 6.6 — Deploy and verify

```powershell
kubectl apply -f .\k8s\
kubectl get pods
kubectl get services
kubectl logs deployment/<api-deployment-name>
kubectl logs deployment/<worker-deployment-name>
```

Use your actual resource names. Port-forward the API for private testing:

```powershell
kubectl port-forward service/<api-service-name> 5001:5001
```

Open `http://localhost:5001/docs`, submit a conversion, and confirm a worker completes it.

## Step 6.7 — Prove reproducibility

Change a non-secret configuration value in Git, re-apply it, and verify the Deployment reaches a healthy state. Record the image versions, commands, and teardown instructions.

**Phase 6 is complete when:** conversion works in Kubernetes, API/Redis/workers are distinct resources, Terraform reproduces the infrastructure, and Redis is not publicly exposed.

---

# Phase 7 — Observability before autoscaling

## Step 7.1 — Define what must be observable

At minimum, collect successful/failed conversions, request rate, conversion duration, end-to-end latency, queue length/oldest age, worker replicas/restarts, CPU, and memory. If an LLM stage is present, also track inference latency and schema failures.

Do not assume Docling exposes every metric in Prometheus format. Check the deployed version. If a needed metric is absent, instrument the project-owned client/gateway or build a small exporter instead of inventing a metrics endpoint.

## Step 7.2 — Deploy Prometheus and Grafana

For local Kubernetes, use a maintained Helm distribution; on AKS install them only for the experiment window or evaluate an appropriate managed option. Configure scrape targets only for components that actually expose metrics. Ensure queue-depth metrics come from a supported exporter/instrumentation path.

Create dashboards for request rate, failures, p50/p95 latency, queue length/age, worker replicas, and resource use. Annotate dashboard screenshots or test times so they can be matched to load runs.

## Step 7.3 — Add tracing

If you own a FastAPI gateway or test service, instrument it with OpenTelemetry. Correlate request submission, task ID, status polling and result retrieval. Never attach private document contents or credentials to trace attributes.

Use traces to determine whether time was spent waiting in queue, converting, running an optional model, or returning the result.

## Step 7.4 — Define an initial SLO

Pick a repeatable workload and set a target for completion success rate and p95 completion time. Measure the static-worker baseline before changing the scaler. Explain what workload the SLO applies to.

## Step 7.5 — Write two runbooks

**Queue backlog rising:** confirm backlog/oldest age; check workers/readiness; inspect logs and restarts; check Redis connectivity and resource limits; scale manually only if safe; verify the backlog recovers; record the cause.

**Conversions failing:** compare API response/worker logs by task ID; distinguish invalid inputs from systemic failures; check Redis and worker availability; retry a known-good sample; verify failure rate returns to baseline.

**Phase 7 is complete when:** dashboards display reliable metrics, at least two actionable thresholds/alerts exist, and the runbooks have been tested during controlled failures.

---

# Phase 8 — KEDA worker autoscaling

## Step 8.1 — Verify the actual Redis queue list

Before configuring KEDA, make sure the list key grows when jobs are queued. For the default `convert` queue, `rq:queue:convert` is common, but verify it for your pinned RQ/Docling version and queue configuration.

Local Compose check:

```powershell
docker compose exec redis redis-cli --scan --pattern "rq:queue:*"
docker compose exec redis redis-cli LLEN rq:queue:convert
```

Use the actual key you observe, not a guessed key.

## Step 8.2 — Install KEDA

Follow the [official KEDA installation guide](https://keda.sh/docs/latest/deploy/) for your cluster/version. Confirm KEDA pods are healthy before creating a ScaledObject.

## Step 8.3 — Create a ScaledObject

Template only: replace the Deployment name, Redis DNS name, key, auth settings and threshold with verified values.

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: docling-workers-scaler
  namespace: default
spec:
  scaleTargetRef:
    name: docling-serve-rq-workers
  minReplicaCount: 1
  maxReplicaCount: 5
  cooldownPeriod: 120
  triggers:
    - type: redis
      metadata:
        address: docling-serve-redis-service.default.svc.cluster.local:6379
        listName: rq:queue:convert
        listLength: "5"
        activationListLength: "0"
```

Important:

- `scaleTargetRef.name` must match the worker Deployment.
- Redis address must be reachable from KEDA inside the cluster.
- `listName` must match the real queue key.
- If Redis uses password/TLS, put credentials in a Kubernetes Secret and configure KEDA TriggerAuthentication; do not hard-code them in YAML.
- Start with one minimum worker while debugging. Test scale-to-zero only later because model loading/cold starts can delay work.
- `listLength` is a scaler target, not a guarantee about completion time; tune it with measurements.

## Step 8.4 — Apply and observe

```powershell
kubectl apply -f .\k8s\keda-scaledobject.yaml
kubectl get scaledobject
kubectl get hpa
kubectl get pods -w
```

Submit a batch. Watch the queue length and pod count increase, then stop submissions and watch scale-in after cooldown. Confirm new pods become ready and consume work.

## Step 8.5 — Compare static and KEDA scaling

Run the same batch with one fixed worker, two fixed workers, and KEDA-based scaling. Compare throughput, total completion time, oldest-job age, worker replicas, failures, CPU/memory and estimated cost. Document workload size and environment.

## Step 8.6 — Optional scale-to-zero test

Only after normal scaling works, set minimum replicas to zero if cold-start latency is acceptable. Verify that a queued job wakes workers and completes within the target. Do not confuse zero worker pods with zero node cost.

**Phase 8 is complete when:** queue backlog triggers scale-out, idle periods trigger safe scale-in, no work is lost in tests, and results are documented.

---

# Phase 9 — Optional KServe, vLLM and GPU model serving

Do this only after CPU document processing, evaluation, CI, observability and KEDA work reliably.

## Step 9.1 — Prove the LLM adds value locally

Run the pretrained model on the labelled dataset. Compare quality, schema validity, latency, memory and failures. Keep the LLM stage only if it improves the defined task.

## Step 9.2 — Validate serving compatibility

Use vLLM only if the model architecture, precision and hardware are supported. Use KServe only after confirming the selected serving runtime and Kubernetes version are compatible. Pin the model revision and container image; add a smoke test that checks output schema and health. An arbitrary Hugging Face model is not automatically supported by every vLLM/KServe setup.

## Step 9.3 — Benchmark before paying for GPUs

Measure model loading time, p50/p95 latency, throughput, peak memory, quality, and estimated cost per completed document. Check current Azure regional availability, VM SKU pricing and quota first. Run GPU tests during a short planned window and remove those resources afterward.

## Step 9.4 — Understand pod versus node autoscaling

KEDA scales pods. AKS Cluster Autoscaler manages eligible nodes when pods cannot be scheduled or nodes can safely be removed. If a GPU pool is added, test the pool's minimum/maximum and scale-down settings separately. An idle GPU VM can still cost money even when the model Deployment has zero replicas. See [AKS cluster autoscaler documentation](https://learn.microsoft.com/en-us/azure/aks/cluster-autoscaler).

**Phase 9 is complete when:** model benefit is measured, serving compatibility is verified, CPU/GPU data exists before GPU spend, and both pod/node behavior is tested.

---

# Phase 10 — Final portfolio evidence

## Step 10.1 — Run a repeatable final benchmark

Use the same input documents/workload for the static-worker and KEDA cases. Report number of documents/pages, completions/failures, throughput, p50/p95 latency, queue wait/oldest age, worker replica range, CPU/memory (and GPU if used), test duration, and cost assumptions.

## Step 10.2 — Finish the README

Include the problem statement, architecture diagram, local setup commands, endpoint behavior, evaluation methodology, MLflow results, load-test results, dashboards, incident example, Terraform apply/destroy instructions, known limitations and next steps.

## Step 10.3 — Only publish measured claims

Examples after you have evidence:

- Implemented Redis/RQ asynchronous document processing.
- Compared static and queue-driven worker scaling under a repeatable workload.
- Tracked pretrained extraction evaluation runs and enforced a CI quality threshold.
- Instrumented queue depth, latency, failures and worker replicas.

Do not claim a specific throughput, uptime, quality score, percentage improvement, or GPU cost saving unless you measured it and can explain the experiment.

## Step 10.4 — Tear down temporary resources

Before finishing a cloud test session, inspect AKS node pools and VMs, delete temporary GPU resources, stop/destroy temporary clusters if no longer needed, retain sanitized reports and Terraform state safely, and verify that no unexpected paid resources remain.

---

# 3. Local-to-Azure execution order

Follow the guide sequentially; do not provision Azure resources until local tests pass.

1. **Start fresh:** Phase 0 checks Docker, removes the old single container, and creates the project workspace.
2. **Validate conversion:** Phase 1 makes one synchronous request and saves its response and timing.
3. **Validate async processing:** Phase 2 configures Redis/RQ and saves an async result.
4. **Measure the system:** Phase 3 adds Python tests and batch reports.
5. **Add MLflow only when useful:** Phase 4 is conditional on having a meaningful evaluation task, such as pretrained invoice-field extraction.
6. **Automate and deploy:** Phase 5 establishes CI/CD; Phase 6 provisions a small CPU-only AKS deployment with Terraform.
7. **Observe and scale:** Phases 7–8 add metrics and KEDA.
8. **Optional advanced work:** Phase 9 explores KServe/vLLM/GPU only if measurements justify the complexity and cost.
9. **Package evidence:** Phase 10 records benchmark results, runbooks, and resource teardown instructions.

Before moving to Azure, all of these should be true: the local API health check works, one sample converts successfully, an async job completes through Redis/RQ, and you have a small batch report. For any failure, inspect `docker compose ps` and the API/worker logs before moving to another layer.

# 4. Official references

- [Docling Serve repository and v1 API](https://github.com/docling-project/docling-serve)
- [Docling Serve deployment guide](https://docling-project.github.io/docling/usage/api_server/deployment/)
- [Docling Serve configuration](https://github.com/docling-project/docling-serve/blob/main/docs/configuration.md)
- [Docling Serve Kubernetes examples](https://github.com/docling-project/docling-serve/tree/main/docs/deploy-examples)
- [RQ documentation](https://python-rq.org/docs/)
- [MLflow Tracking](https://mlflow.org/docs/latest/tracking/)
- [KEDA Redis Lists scaler](https://keda.sh/docs/latest/scalers/redis-lists/)
- [KEDA installation](https://keda.sh/docs/latest/deploy/)
- [KServe](https://kserve.github.io/website/)
- [vLLM](https://docs.vllm.ai/)
- [Terraform AzureRM provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs)
- [Azure Kubernetes Service](https://learn.microsoft.com/en-us/azure/aks/)
- [AKS cluster autoscaler](https://learn.microsoft.com/en-us/azure/aks/cluster-autoscaler)
- [Prometheus](https://prometheus.io/docs/)
- [Grafana](https://grafana.com/docs/)
- [OpenTelemetry](https://opentelemetry.io/docs/)

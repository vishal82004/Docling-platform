# SRE / DevOps Runbook: Kubernetes Deployment & Infrastructure as Code

**Platform:** Elastic Document Intelligence Platform  
**Target Architecture:** Azure AKS + Terraform + Kubernetes  
**Status:** Validated locally (No cloud actions executed)  

---

## 1. Prerequisites Checklist

Before provisioning resources in Azure:
- [ ] Azure CLI installed (`az version`)
- [ ] Terraform installed (`terraform version >= 1.5`)
- [ ] Kubectl installed (`kubectl version --client`)
- [ ] Active Azure subscription with sufficient vCPU quota for 2x `Standard_D2s_v5` VMs

---

## 2. Infrastructure as Code (Terraform)

All Terraform configurations reside in [`infra/terraform/`](file:///c:/Users/vishal/docling-platform-local/infra/terraform/):
- `providers.tf`: Configures the HashiCorp AzureRM provider (`~> 3.110.0`).
- `variables.tf`: Defines region (`eastus`), node count (`2`), VM size (`Standard_D2s_v5`), and tags.
- `main.tf`: Declares Resource Group, Virtual Network (`10.0.0.0/16`), Subnet (`10.0.1.0/24`), and the AKS cluster.
- `outputs.tf`: Exports cluster name, resource group, and connection commands.

### Local Validation Commands:
```powershell
cd infra/terraform
terraform fmt -check
terraform init -backend=false
terraform validate
```

### When Ready to Provision in Azure:
```powershell
# 1. Log in to Azure and confirm active subscription
az login
az account show --output table

# 2. Review execution plan
terraform plan -out=tfplan

# 3. Apply the infrastructure
terraform apply tfplan

# 4. Fetch AKS credentials
az aks get-credentials --resource-group rg-docling-platform-dev --name aks-docling-platform-dev
```

---

## 3. Kubernetes Deployment (`k8s/`)

The platform manifests reside in [`k8s/`](file:///c:/Users/vishal/docling-platform-local/k8s/):
- `namespace.yaml`: Creates dedicated namespace `docling-platform`.
- `configmap.yaml`: Injects Redis connection URL and queue name (`convert`).
- `redis.yaml`: Deploys Redis 7 with private `ClusterIP` on port 6379 (never publicly exposed).
- `docling-api.yaml`: Ingestion API deployment with liveness/readiness probes on `/health`.
- `docling-worker.yaml`: Scalable RQ consumer pool (2 replicas baseline, 1.2Gi memory request each).
- `kustomization.yaml`: Bundles all manifests for atomic deployment.

### Local Syntax Verification:
```powershell
kubectl kustomize k8s/
```

### Applying to Kubernetes Cluster:
```powershell
# Deploy all resources atomically
kubectl apply -k k8s/

# Verify rollout status
kubectl get pods -n docling-platform -w
kubectl get services -n docling-platform
```

---

## 4. End-to-End Verification via Port-Forward

To verify the cluster without exposing public IPs:
```powershell
# Forward API service port locally
kubectl port-forward -n docling-platform svc/docling-api 5001:5001

# Run the automated smoke test in another terminal
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

---

## 5. Clean Teardown & Cost Elimination

To avoid incurring ongoing cloud costs when finished testing:
```powershell
# 1. Delete Kubernetes resources
kubectl delete -k k8s/

# 2. Destroy all Azure infrastructure via Terraform
cd infra/terraform
terraform destroy -auto-approve
```

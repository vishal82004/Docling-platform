# Phase 4 — MLOps Evaluation, MLflow Tracking & Quality Gate Report

**Generated:** 2026-10-30  
**Dataset:** `invoice-eval-v1` (25 synthetic invoices with diverse layouts, date formats, and edge cases)  
**MLflow Experiment:** `docling-invoice-extraction`  
**Evaluation Engine:** `evaluation/evaluate.py`  

---

## 1. Executive Summary

Phase 4 establishes an automated **MLOps evaluation and quality gating harness** that evaluates downstream structured extraction against converted documents. 

- **Target Schema:** Strict JSON output (`invoice_number`, `vendor`, `invoice_date`, `total`).
- **Standardized Normalization:** Case-insensitive string matching, legal suffix removal (`Inc.`, `LLC`, `Ltd.`), date canonicalization to ISO `YYYY-MM-DD`, and float total comparison ($\pm 0.01$ tolerance).
- **MLflow Tracking:** All runs log hyperparameters, metrics, and error artifacts (`report.json`, `errors.json`) to a local MLflow tracking registry.
- **CI/CD Quality Gate:** `evaluate.py` enforces automated SLOs (`--min-field-acc`, `--min-schema-valid`, `--min-exact-match`, `--max-p95-latency`). Regressive candidates trigger a non-zero exit code (`1`), blocking CI promotion.

---

## 2. Candidate Comparison Table

| Metric | Target Threshold | Candidate 1: Baseline (`extraction-v1`) | Candidate 2: Flawed (`extraction-flawed`) | Gate Decision |
|---|---|---|---|---|
| **Schema Validity Rate** | $\ge 95.0\%$ | **100.0%** | **0.0%** | Baseline Passed / Flawed Failed |
| **Overall Field Accuracy** | $\ge 85.0\%$ | **97.0%** | **25.0%** | Baseline Passed / Flawed Failed |
| **Exact Record Match Rate** | $\ge 75.0\%$ | **88.0%** | **0.0%** | Baseline Passed / Flawed Failed |
| **Failure / Exception Rate** | $\le 5.0\%$ | **0.0%** | **0.0%** | Both Passed |
| **Invoice Number Accuracy** | N/A | **100.0%** | 4.0% | Major Regression |
| **Vendor Accuracy** | N/A | **96.0%** | 88.0% | Slight Regression |
| **Invoice Date Accuracy** | N/A | **92.0%** | 4.0% | Major Regression |
| **Total Amount Accuracy** | N/A | **100.0%** | 4.0% | Major Regression |
| **p50 Latency** | N/A | 15.5 ms | 10.2 ms | Both fast |
| **p95 Latency** | $\le 5.0$ s | 16.4 ms | 10.6 ms | Both Passed |
| **Quality Gate Status** | All must pass | **PASSED (Exit Code 0)** | **FAILED (Exit Code 1)** | **Gate Protected** |

---

## 3. Analysis & Key Takeaways

1. **Gate Reliability:**  
   The baseline candidate achieved **97% overall accuracy** and **100% schema compliance**, successfully passing all thresholds and exiting with code `0`.  
   The flawed candidate regressed to **25% field accuracy** and **0% schema compliance** due to loose keys and unnormalized dates/currency symbols, causing the gate to abort with exit code `1`.
2. **MLflow Tracking Registry:**  
   Both candidate runs, along with their parameters, metrics, and diagnostic JSON error diffs, are permanently registered in MLflow under the `docling-invoice-extraction` experiment.
3. **Foundation for Phase 5 (CI/CD):**  
   The automated gate check `python evaluation/evaluate.py --candidate baseline --min-field-acc 0.85` can now be integrated directly into GitHub Actions to block pull requests that cause extraction regressions.

---

## 4. How to Inspect Runs in the MLflow UI

To launch the local MLflow dashboard:

```powershell
.\.venv\Scripts\mlflow.exe server --host 127.0.0.1 --port 5000
```

Then open `http://127.0.0.1:5000` in your browser to view side-by-side run comparisons, parameter diffs, and metric curves.


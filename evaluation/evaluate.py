#!/usr/bin/env python3
"""
MLOps Evaluation Harness for Document Intelligence Platform.
Evaluates structured extraction quality from converted invoice documents against ground truth,
tracks runs & metrics in MLflow, and enforces CI/CD quality gates.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"

# Try importing MLflow (optional fallback if not yet installed)
try:
    import mlflow

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

EVAL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVAL_DIR.parent
DEFAULT_DATASET_DIR = EVAL_DIR / "dataset" / "invoice-eval-v1"
DEFAULT_REPORTS_DIR = EVAL_DIR / "reports"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

try:
    from vllm_client import VLLMClient
except ImportError:
    try:
        from scripts.vllm_client import VLLMClient
    except ImportError:
        VLLMClient = None


def resolve_mlflow_tracking_uri(explicit_uri: Optional[str] = None) -> Optional[str]:
    """Resolve MLflow tracking URI: explicit argument > env var > local container > None (local ./mlruns)."""
    if explicit_uri:
        return explicit_uri
    if os.environ.get("MLFLOW_TRACKING_URI"):
        return os.environ["MLFLOW_TRACKING_URI"]
    # Check if local MLflow server container is running on port 5000
    try:
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:5000/health", timeout=0.5) as resp:
            if resp.status == 200:
                return "http://127.0.0.1:5000"
    except Exception:
        pass
    return None


# =====================================================================
# 1. Normalization & Comparison Helpers
# =====================================================================


def normalize_vendor_name(vendor: Optional[str]) -> Optional[str]:
    """Normalize vendor name by stripping legal entity suffixes and punctuation."""
    if not vendor:
        return None
    v = vendor.strip().lower()
    # Strip common legal suffixes
    legal_suffixes = [
        r"\bllc\b",
        r"\bltd\b",
        r"\bltd\.\b",
        r"\binc\b",
        r"\binc\.\b",
        r"\bcorp\b",
        r"\bcorp\.\b",
        r"\bgmbh\b",
        r"\bco\b",
        r"\bco\.\b",
    ]
    for s in legal_suffixes:
        v = re.sub(s, "", v)
    # Strip punctuation and extra whitespace
    v = re.sub(r"[^\w\s]", "", v)
    v = re.sub(r"\s+", " ", v).strip()
    return v if v else None


def normalize_invoice_number(inv_num: Optional[str]) -> Optional[str]:
    """Normalize invoice number by stripping common prefixes and whitespace."""
    if not inv_num:
        return None
    s = str(inv_num).strip().upper()
    prefixes = [
        "INVOICE NUMBER:",
        "INVOICE NO:",
        "INVOICE #:",
        "INVOICE #",
        "INVOICE REF:",
        "BILL NUMBER:",
        "BILL NO:",
        "REFERENCE:",
        "REF:",
    ]
    for p in prefixes:
        if s.startswith(p):
            s = s[len(p) :].strip()
    return s if s else None


def normalize_date(date_str: Optional[str]) -> Optional[str]:
    """
    Normalize diverse date strings into standard ISO 'YYYY-MM-DD'.
    Handles formats:
      - 2026-01-15, 2026.04.12
      - 18/02/2026, 05-20-2026, 03.11.2026, 12/05/2026, 05/09/2026, 11/08/2026
      - January 15, 2026, March 4, 2026, July 19, 2026, June 25, 2026, Dec 15, 2026
      - Sep 09, 2026, Nov 2, 2026, 14 Feb 2026
    """
    if not date_str:
        return None
    d = str(date_str).strip()

    # Match ISO: YYYY-MM-DD or YYYY.MM.DD
    m_iso = re.match(r"^(\d{4})[-.](\d{1,2})[-.](\d{1,2})$", d)
    if m_iso:
        y, m, day = m_iso.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(day):02d}"

    # Month names mapping
    months = {
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }

    # Match "Month Day, Year" or "Month Day Year"
    m_text = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$", d)
    if m_text:
        mon_str, day, y = m_text.groups()
        mon_idx = months.get(mon_str.lower())
        if mon_idx:
            return f"{int(y):04d}-{mon_idx:02d}-{int(day):02d}"

    # Match "Day Month Year" e.g. "14 Feb 2026"
    m_text_rev = re.match(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$", d)
    if m_text_rev:
        day, mon_str, y = m_text_rev.groups()
        mon_idx = months.get(mon_str.lower())
        if mon_idx:
            return f"{int(y):04d}-{mon_idx:02d}-{int(day):02d}"

    # Match DD/MM/YYYY, MM/DD/YYYY, or DD.MM.YYYY
    m_slash = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$", d)
    if m_slash:
        n1, n2, y = [int(x) for x in m_slash.groups()]
        # Disambiguation: if n1 > 12, it must be DD/MM/YYYY
        if n1 > 12:
            return f"{y:04d}-{n2:02d}-{n1:02d}"
        # If n2 > 12, it must be MM/DD/YYYY
        if n2 > 12:
            return f"{y:04d}-{n1:02d}-{n2:02d}"
        # Default convention in our dataset: DD/MM/YYYY unless known US format
        # Check standard convention
        return f"{y:04d}-{n2:02d}-{n1:02d}"

    return d


def normalize_total(total_val: Any) -> Optional[float]:
    """Convert number/string into rounded 2-decimal float."""
    if total_val is None:
        return None
    if isinstance(total_val, (int, float)):
        return round(float(total_val), 2)
    s = str(total_val).strip()
    s = re.sub(r"[^\d.-]", "", s.replace(",", ""))
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def compare_fields(extracted: Dict[str, Any], ground_truth: Dict[str, Any]) -> Tuple[Dict[str, bool], bool]:
    """
    Compare extracted fields against ground truth with domain-specific normalization.
    Returns (field_matches_dict, exact_record_match).
    """
    matches = {}

    # 1. Invoice Number
    ext_inv = normalize_invoice_number(extracted.get("invoice_number"))
    gt_inv = normalize_invoice_number(ground_truth.get("invoice_number"))
    matches["invoice_number"] = ext_inv == gt_inv

    # 2. Vendor
    ext_vendor = normalize_vendor_name(extracted.get("vendor"))
    gt_vendor = normalize_vendor_name(ground_truth.get("vendor"))
    matches["vendor"] = ext_vendor == gt_vendor

    # 3. Invoice Date
    ext_date = normalize_date(extracted.get("invoice_date"))
    gt_date = normalize_date(ground_truth.get("invoice_date"))
    matches["invoice_date"] = ext_date == gt_date

    # 4. Total
    ext_tot = normalize_total(extracted.get("total"))
    gt_tot = normalize_total(ground_truth.get("total"))
    if ext_tot is None and gt_tot is None:
        matches["total"] = True
    elif ext_tot is not None and gt_tot is not None:
        matches["total"] = abs(ext_tot - gt_tot) <= 0.01
    else:
        matches["total"] = False

    exact_record = all(matches.values())
    return matches, exact_record


# =====================================================================
# 2. Candidate Extraction Engines
# =====================================================================


class BaselineExtractor:
    """
    High-accuracy baseline extractor conforming to extraction-v1.txt.
    Extracts invoice fields using structured heuristics & regex modeling Docling downstream outputs.
    """

    def extract(self, text: str) -> Tuple[Dict[str, Any], bool, Optional[str]]:
        """Returns (result_dict, is_schema_valid, error_msg)."""
        time.sleep(0.015)  # Simulate small extraction computation time

        # Clean markdown formatting artifacts for robust extraction
        clean_text = text.replace("**", "").replace("__", "")

        data = {"invoice_number": None, "vendor": None, "invoice_date": None, "total": None}

        # 1. Extract Vendor (First prominent heading or company title)
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        for line in lines[:5]:
            clean_line = re.sub(r"^#+\s*", "", line).strip()
            if not any(
                k in clean_line.lower()
                for k in [
                    "invoice",
                    "tax invoice",
                    "commercial invoice",
                    "receipt",
                    "order receipt",
                    "bill to",
                    "statement",
                ]
            ):
                if len(clean_line) > 3 and not clean_line.lower().startswith("date"):
                    vendor_candidate = clean_line.split(",")[0].split("-")[0].strip()
                    data["vendor"] = vendor_candidate
                    break

        # 2. Extract Invoice Number
        inv_patterns = [
            r"(?i)\b(?:Invoice\s*(?:Number|No|#|ID|Ref)?|Bill\s*(?:Number|No)?|Reference|Ref|Rechnung(?:\s*/\s*Invoice)?)\s*[:#]\s*([A-Za-z0-9-]+)",
            r"(?i)\bINVOICE\s*:\s*([A-Za-z0-9-]+)",
            r"(?i)\bBill\s*Number\s*:\s*([A-Za-z0-9-]+)",
            r"(?i)\bBill\s*No\s*:\s*([A-Za-z0-9-]+)",
        ]
        invalid_tokens = {"to", "number", "no", "date", "id", "ref", "of", "due"}
        for pat in inv_patterns:
            m = re.search(pat, clean_text)
            if m:
                val = m.group(1).strip()
                if val.lower() not in invalid_tokens:
                    data["invoice_number"] = val
                    break

        # 3. Extract Invoice Date
        date_patterns = [
            r"(?i)\b(?:Invoice\s*Date|Date\s*of\s*Issue|Date\s*of\s*Invoice|Billing\s*Date|DATE\s*OF\s*BILL|Datum|Issue\s*Date|Date)\s*[:#]\s*([A-Za-z0-9/.,\s-]+?)(?:\n|$|\s{2,}|Customer|Payment|Due|Job|Tax|Event)",
        ]
        for pat in date_patterns:
            m = re.search(pat, clean_text)
            if m:
                d_cand = m.group(1).strip()
                d_cand = re.sub(r"\(.*?\)", "", d_cand).strip()
                if d_cand and not any(w in d_cand.lower() for w in ["unprinted", "due", "paid"]):
                    normalized_d = normalize_date(d_cand)
                    if normalized_d and re.match(r"^\d{4}-\d{2}-\d{2}$", normalized_d):
                        data["invoice_date"] = normalized_d
                        break

        # 4. Extract Total
        total_patterns = [
            r"(?i)\b(?:TOTAL\s*AMOUNT\s*DUE|Grand\s*Total\s*Due|Final\s*Balance\s*Due|Net\s*Amount\s*Payable|Net\s*Payable\s*Total|Total\s*Payable|Balance\s*Due|Total\s*USD\s*Due|Gesamtbetrag\s*/\s*Total|Grand\s*Total|Invoice\s*Total|Amount\s*Outstanding|Amount\s*Paid|Total\s*Charges|Total\s*Balance|Total\s*Amount|Total\s*Due|Total\s*Professional\s*Fee|Total)\s*[:#]?\s*[\$€£]?\s*([0-9,]+\.[0-9]{2})",
        ]
        for pat in total_patterns:
            m = re.search(pat, clean_text)
            if m:
                raw_amt = m.group(1).replace(",", "")
                try:
                    data["total"] = float(raw_amt)
                    break
                except ValueError:
                    pass

        # Validate schema conformance
        is_valid = True
        err = None
        if not isinstance(data.get("invoice_number"), (str, type(None))):
            is_valid = False
        if not isinstance(data.get("vendor"), (str, type(None))):
            is_valid = False
        if not isinstance(data.get("invoice_date"), (str, type(None))):
            is_valid = False
        if data.get("total") is not None and not isinstance(data.get("total"), (int, float)):
            is_valid = False

        return data, is_valid, err


class FlawedExtractor:
    """
    Deliberately degraded candidate conforming to extraction-flawed.txt.
    Demonstrates quality gate failure in CI/CD by regressing on:
    - Date normalization (leaves unparsed localized date strings)
    - Total parsing (leaves currency symbols/commas, violating schema)
    - Vendor normalization (leaves dirty tokens and missing fields)
    """

    def extract(self, text: str) -> Tuple[Dict[str, Any], bool, Optional[str]]:
        time.sleep(0.010)

        # Deliberate flaws: unparsed raw strings, invalid types
        data = {
            "invoice": None,  # Wrong key name! Schema violation
            "vendor": None,
            "date": None,  # Wrong key name! Schema violation
            "total": "$1,450.75",  # Raw unparsed string with currency symbol!
        }

        # Naive vendor grab
        first_line = text.splitlines()[0] if text else ""
        data["vendor"] = first_line.replace("#", "").strip()

        # Schema is deliberately invalid because key names and total type violate schema
        is_valid = False
        error_msg = "Schema violation: missing required keys ['invoice_number', 'invoice_date'], 'total' is not float"

        return data, is_valid, error_msg


class VLLMExtractor:
    """
    Production LLM extraction candidate utilizing vLLM's OpenAI-compatible serving engine.
    Applies Pydantic data contract validation to extract structured invoice entities.
    """

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        if VLLMClient is None:
            raise ImportError("VLLMClient is not available. Ensure scripts/vllm_client.py is on sys.path.")
        kwargs: Dict[str, Any] = {}
        if base_url:
            kwargs["base_url"] = base_url
        if model:
            kwargs["model"] = model
        self.client = VLLMClient(**kwargs)

    def extract(self, text: str) -> Tuple[Dict[str, Any], bool, Optional[str]]:
        try:
            extraction = self.client.extract_from_markdown(text)
            data = {
                "invoice_number": extraction.invoice_number,
                "vendor": extraction.vendor,
                "invoice_date": extraction.invoice_date,
                "total": extraction.total,
            }
            # Validate schema conformance
            is_valid = True
            err = None
            if not isinstance(data.get("invoice_number"), (str, type(None))):
                is_valid = False
            if not isinstance(data.get("vendor"), (str, type(None))):
                is_valid = False
            if not isinstance(data.get("invoice_date"), (str, type(None))):
                is_valid = False
            if data.get("total") is not None and not isinstance(data.get("total"), (int, float)):
                is_valid = False

            return data, is_valid, err
        except Exception as e:
            return {}, False, str(e)


# =====================================================================
# 3. Main Evaluation Runner
# =====================================================================


def run_evaluation(
    candidate: str = "baseline",
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    min_field_acc: float = 0.85,
    min_schema_valid: float = 0.95,
    min_exact_match: float = 0.75,
    max_failure_rate: float = 0.05,
    max_p95_latency: float = 5.0,
    experiment_name: str = "docling-invoice-extraction",
    tracking_uri: Optional[str] = None,
) -> Tuple[Dict[str, Any], bool]:
    """
    Run evaluation across all documents, compute metrics, log to MLflow,
    and enforce quality gate thresholds.
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = dataset_dir / "documents"
    ground_truth_path = dataset_dir / "ground_truth.jsonl"

    if not ground_truth_path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {ground_truth_path}")

    # Load ground truth
    ground_truth_map: Dict[str, Dict[str, Any]] = {}
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                ground_truth_map[item["doc_id"]] = item

    # Initialize candidate extractor
    if candidate == "baseline":
        extractor = BaselineExtractor()
        prompt_version = "extraction-v1"
    elif candidate == "flawed":
        extractor = FlawedExtractor()
        prompt_version = "extraction-flawed"
    elif candidate == "vllm":
        extractor = VLLMExtractor()
        prompt_version = "extraction-vllm-qwen"
    else:
        raise ValueError(f"Unknown candidate extractor: {candidate}")

    # Initialize MLflow experiment and tracking URI if available
    mlflow_active = False
    if MLFLOW_AVAILABLE:
        try:
            resolved_uri = resolve_mlflow_tracking_uri(tracking_uri)
            if resolved_uri:
                mlflow.set_tracking_uri(resolved_uri)
            mlflow.set_experiment(experiment_name)
            mlflow_active = True
        except Exception as mlf_init_err:
            print(f"[MLflow WARN] Failed to initialize MLflow tracking: {mlf_init_err}")

    print("=" * 68)
    print(f"MLOps Evaluation Run — Candidate: '{candidate}' | Dataset: {dataset_dir.name}")
    print(f"Total Evaluation Documents: {len(ground_truth_map)}")
    print("=" * 68)

    results: List[Dict[str, Any]] = []
    latencies: List[float] = []
    field_match_counts = {"invoice_number": 0, "vendor": 0, "invoice_date": 0, "total": 0}
    exact_matches = 0
    schema_valid_count = 0
    failures = 0
    errors_list: List[Dict[str, Any]] = []

    start_eval_time = time.perf_counter()

    for doc_id, gt in ground_truth_map.items():
        doc_file = docs_dir / f"{doc_id}.md"
        if not doc_file.exists():
            print(f"[WARN] Document file missing: {doc_file}")
            failures += 1
            continue

        with open(doc_file, "r", encoding="utf-8") as df:
            doc_text = df.read()

        t0 = time.perf_counter()
        try:
            if mlflow_active and hasattr(mlflow, "start_span"):
                try:
                    with mlflow.start_span(name=f"extract_invoice_{doc_id}") as span:
                        span.set_inputs({"doc_id": doc_id, "candidate": candidate, "text_preview": doc_text[:250]})
                        extracted_json, is_schema_valid, extract_err = extractor.extract(doc_text)
                        span.set_outputs(
                            {
                                "doc_id": doc_id,
                                "extracted": extracted_json,
                                "schema_valid": is_schema_valid,
                                "error": extract_err,
                            }
                        )
                except Exception:
                    extracted_json, is_schema_valid, extract_err = extractor.extract(doc_text)
            else:
                extracted_json, is_schema_valid, extract_err = extractor.extract(doc_text)
            elapsed = time.perf_counter() - t0
            latencies.append(elapsed)

            if is_schema_valid:
                schema_valid_count += 1

            matches, exact_match = compare_fields(extracted_json, gt)
            if exact_match:
                exact_matches += 1

            for field_name, is_match in matches.items():
                if is_match:
                    field_match_counts[field_name] += 1

            doc_record = {
                "doc_id": doc_id,
                "is_schema_valid": is_schema_valid,
                "exact_match": exact_match,
                "field_matches": matches,
                "latency_sec": round(elapsed, 4),
                "extracted": extracted_json,
                "ground_truth": {k: gt.get(k) for k in ["invoice_number", "vendor", "invoice_date", "total"]},
                "error": extract_err,
            }
            results.append(doc_record)

            if not exact_match or not is_schema_valid:
                errors_list.append(doc_record)

            status_icon = "PASS" if exact_match else ("WARN" if is_schema_valid else "FAIL")
            print(
                f"[{status_icon:4s}] Doc {doc_id} -> exact: {exact_match}, schema_valid: {is_schema_valid} ({elapsed * 1000:.1f}ms)"
            )

        except Exception as exc:
            elapsed = time.perf_counter() - t0
            latencies.append(elapsed)
            failures += 1
            errors_list.append({"doc_id": doc_id, "error": str(exc), "exception": True})
            print(f"[FAIL] Doc {doc_id} -> Exception: {exc}")

    total_eval_elapsed = time.perf_counter() - start_eval_time
    total_docs = len(ground_truth_map)

    # Compute Aggregate Metrics
    schema_valid_rate = round(schema_valid_count / total_docs, 4) if total_docs else 0.0
    exact_match_rate = round(exact_matches / total_docs, 4) if total_docs else 0.0
    failure_rate = round(failures / total_docs, 4) if total_docs else 0.0

    field_accuracies = {field: round(count / total_docs, 4) for field, count in field_match_counts.items()}
    overall_field_accuracy = round(sum(field_accuracies.values()) / len(field_accuracies), 4)

    # Calculate Latency Percentiles
    sorted_latencies = sorted(latencies) if latencies else [0.0]
    n_lat = len(sorted_latencies)
    p50_latency = round(sorted_latencies[int(n_lat * 0.50)], 4)
    p95_latency = round(sorted_latencies[min(int(n_lat * 0.95), n_lat - 1)], 4)

    # Quality Gate Evaluation
    gate_checks = {
        "min_field_accuracy": {
            "target": min_field_acc,
            "actual": overall_field_accuracy,
            "passed": overall_field_accuracy >= min_field_acc,
        },
        "min_schema_valid_rate": {
            "target": min_schema_valid,
            "actual": schema_valid_rate,
            "passed": schema_valid_rate >= min_schema_valid,
        },
        "min_exact_match_rate": {
            "target": min_exact_match,
            "actual": exact_match_rate,
            "passed": exact_match_rate >= min_exact_match,
        },
        "max_failure_rate": {
            "target": max_failure_rate,
            "actual": failure_rate,
            "passed": failure_rate <= max_failure_rate,
        },
        "max_p95_latency_sec": {
            "target": max_p95_latency,
            "actual": p95_latency,
            "passed": p95_latency <= max_p95_latency,
        },
    }

    all_gates_passed = all(check["passed"] for check in gate_checks.values())

    report_payload = {
        "evaluation_name": "invoice_extraction_evaluation",
        "candidate": candidate,
        "prompt_version": prompt_version,
        "dataset_version": dataset_dir.name,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_documents": total_docs,
        "total_elapsed_seconds": round(total_eval_elapsed, 4),
        "metrics": {
            "overall_field_accuracy": overall_field_accuracy,
            "exact_match_rate": exact_match_rate,
            "schema_valid_rate": schema_valid_rate,
            "failure_rate": failure_rate,
            "field_accuracies": field_accuracies,
            "latency": {
                "avg_sec": round(sum(latencies) / n_lat, 4),
                "p50_sec": p50_latency,
                "p95_sec": p95_latency,
                "min_sec": round(sorted_latencies[0], 4),
                "max_sec": round(sorted_latencies[-1], 4),
            },
        },
        "quality_gate": {"overall_passed": all_gates_passed, "checks": gate_checks},
        "sample_errors_count": len(errors_list),
    }

    # Save reports
    report_file = reports_dir / f"eval-{candidate}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    errors_file = reports_dir / f"errors-{candidate}.json"
    with open(errors_file, "w", encoding="utf-8") as f:
        json.dump(errors_list, f, indent=2)

    # MLflow Tracking
    if mlflow_active:
        try:
            with mlflow.start_run(run_name=f"{candidate}-{prompt_version}"):
                # Log Params
                mlflow.log_param("candidate", candidate)
                mlflow.log_param("prompt_version", prompt_version)
                mlflow.log_param("dataset_version", dataset_dir.name)
                mlflow.log_param("total_documents", total_docs)
                mlflow.log_param("quality_gate_passed", all_gates_passed)

                # Log Metrics
                mlflow.log_metric("overall_field_accuracy", overall_field_accuracy)
                mlflow.log_metric("exact_match_rate", exact_match_rate)
                mlflow.log_metric("schema_valid_rate", schema_valid_rate)
                mlflow.log_metric("failure_rate", failure_rate)
                mlflow.log_metric("p50_latency_sec", p50_latency)
                mlflow.log_metric("p95_latency_sec", p95_latency)
                for field, acc in field_accuracies.items():
                    mlflow.log_metric(f"field_acc_{field}", acc)

                # Log Artifacts
                mlflow.log_artifact(str(report_file))
                mlflow.log_artifact(str(errors_file))
                current_uri = mlflow.get_tracking_uri()
                print(f"[MLflow] Successfully logged run to experiment '{experiment_name}' at {current_uri}.")
        except Exception as mlf_err:
            print(f"[MLflow WARN] Failed to log to MLflow: {mlf_err}")

    # Print Summary Table
    print("\n" + "=" * 68)
    print(f"EVALUATION SUMMARY: {candidate.upper()}")
    print("=" * 68)
    print(f"Schema Validity Rate:    {schema_valid_rate * 100:.1f}%")
    print(f"Overall Field Accuracy:  {overall_field_accuracy * 100:.1f}%")
    print(f"Exact Record Match:      {exact_match_rate * 100:.1f}%")
    print(f"Failure Rate:            {failure_rate * 100:.1f}%")
    print(f"Per-Field Accuracy:      {field_accuracies}")
    print(f"Latency p50 / p95:       {p50_latency * 1000:.1f}ms / {p95_latency * 1000:.1f}ms")
    print("-" * 68)
    print(f"QUALITY GATE STATUS:     {'PASSED (EXIT 0)' if all_gates_passed else 'FAILED (EXIT 1)'}")
    for check_name, check in gate_checks.items():
        status = "PASSED" if check["passed"] else "FAILED"
        print(f"  - {check_name:<24}: Actual={check['actual']} vs Target={check['target']} -> [{status}]")
    print("=" * 68)
    print(f"Report written to: {report_file}")
    print(f"Errors written to: {errors_file}")

    return report_payload, all_gates_passed


def main():
    parser = argparse.ArgumentParser(description="Document Intelligence MLOps Evaluation Runner")
    parser.add_argument(
        "--candidate", choices=["baseline", "flawed", "vllm"], default="baseline", help="Candidate extraction engine"
    )
    parser.add_argument("--dataset-dir", default=str(DEFAULT_DATASET_DIR), help="Path to evaluation dataset")
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR), help="Path to write reports")
    parser.add_argument("--min-field-acc", type=float, default=0.85, help="Gate: Min field accuracy")
    parser.add_argument("--min-schema-valid", type=float, default=0.95, help="Gate: Min schema validity rate")
    parser.add_argument("--min-exact-match", type=float, default=0.75, help="Gate: Min exact match rate")
    parser.add_argument("--max-failure-rate", type=float, default=0.05, help="Gate: Max failure rate")
    parser.add_argument("--max-p95-latency", type=float, default=5.0, help="Gate: Max p95 latency in seconds")
    parser.add_argument("--experiment-name", default="docling-invoice-extraction", help="MLflow experiment name")
    parser.add_argument(
        "--tracking-uri",
        default=None,
        help="MLflow tracking server URI (defaults to http://127.0.0.1:5000 if running, else local ./mlruns)",
    )

    args = parser.parse_args()

    _, passed = run_evaluation(
        candidate=args.candidate,
        dataset_dir=Path(args.dataset_dir),
        reports_dir=Path(args.reports_dir),
        min_field_acc=args.min_field_acc,
        min_schema_valid=args.min_schema_valid,
        min_exact_match=args.min_exact_match,
        max_failure_rate=args.max_failure_rate,
        max_p95_latency=args.max_p95_latency,
        experiment_name=args.experiment_name,
        tracking_uri=args.tracking_uri,
    )

    if not passed:
        print(
            f"\n[CI/CD QUALITY GATE ERROR] Candidate '{args.candidate}' violated quality thresholds. Exiting with code 1."
        )
        sys.exit(1)

    print(
        f"\n[CI/CD QUALITY GATE SUCCESS] Candidate '{args.candidate}' passed all quality gates. Eligible for release."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()

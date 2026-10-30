#!/usr/bin/env python3
"""
Smoke test script for Docling Serve asynchronous conversion API.
Verifies health, submits an async conversion job, polls to completion,
and writes structured timing & outcome reports to JSON.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path

# Add script directory to sys.path to import client
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from client import DoclingClient, TaskFailedError

DEFAULT_BASE_URL = os.environ.get("DOCLING_BASE_URL", "http://127.0.0.1:5001")
DEFAULT_SAMPLE_URL = "https://arxiv.org/pdf/2501.17887"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "reports" / "phase3-smoke-test.json"


def run_smoke_test(
    base_url: str = DEFAULT_BASE_URL,
    sample_url: str = DEFAULT_SAMPLE_URL,
    timeout: float = 300.0,
    poll_interval: float = 2.0,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict:
    """Execute end-to-end smoke test and return result summary dict."""
    client = DoclingClient(base_url=base_url)
    started_at = datetime.datetime.now(datetime.timezone.utc)
    overall_start = time.perf_counter()

    report = {
        "test_name": "phase3_smoke_test",
        "started_at": started_at.isoformat(),
        "base_url": base_url,
        "sample_url": sample_url,
        "steps": {},
        "success": False,
        "elapsed_seconds": 0.0,
        "error": None,
    }

    try:
        # Step 1: Health check
        print(f"[1/4] Checking API health at {base_url}/health...")
        t0 = time.perf_counter()
        health_res = client.health()
        t1 = time.perf_counter()
        print(f"      Health OK: {health_res} ({t1 - t0:.3f}s)")
        report["steps"]["health_check"] = {
            "status": "passed",
            "latency_seconds": round(t1 - t0, 4),
            "response": health_res,
        }

        # Step 2: Submit async conversion
        print(f"[2/4] Submitting async conversion job for: {sample_url}...")
        payload = client.build_url_payload(sample_url, to_formats=["md"])
        t0 = time.perf_counter()
        submission = client.submit_async(payload)
        t1 = time.perf_counter()
        task_id = submission["task_id"]
        initial_status = submission.get("task_status", "unknown")
        print(f"      Submitted successfully. Task ID: {task_id} (Initial Status: {initial_status}) ({t1 - t0:.3f}s)")
        report["steps"]["submission"] = {
            "status": "passed",
            "latency_seconds": round(t1 - t0, 4),
            "task_id": task_id,
            "initial_status": initial_status,
        }

        # Step 3: Poll until completion
        print(f"[3/4] Polling task {task_id} until completion (max {timeout}s)...")
        t0 = time.perf_counter()
        status_data = client.wait_for_completion(
            task_id=task_id, timeout=timeout, poll_interval=poll_interval, fail_on_error=False
        )
        t1 = time.perf_counter()
        final_status = status_data.get("task_status")
        print(f"      Task reached terminal status: '{final_status}' in {t1 - t0:.2f}s")
        report["steps"]["polling"] = {
            "status": "passed" if final_status == "success" else "failed",
            "polling_duration_seconds": round(t1 - t0, 4),
            "final_task_status": final_status,
            "status_response": status_data,
        }

        if final_status != "success":
            raise TaskFailedError(f"Task finished with non-success status: {final_status}")

        # Step 4: Verify result retrieval
        print(f"[4/4] Verifying result retrieval from /v1/result/{task_id}...")
        t0 = time.perf_counter()
        result_data = client.get_result(task_id)
        t1 = time.perf_counter()
        doc_count = len(result_data.get("documents", [])) if isinstance(result_data, dict) else 0
        print(f"      Result retrieved OK. Documents converted: {doc_count} ({t1 - t0:.3f}s)")
        report["steps"]["result_retrieval"] = {
            "status": "passed",
            "latency_seconds": round(t1 - t0, 4),
            "documents_count": doc_count,
        }

        report["success"] = True

    except Exception as exc:
        print(f"[ERROR] Smoke test failed: {exc}", file=sys.stderr)
        report["error"] = str(exc)
        report["success"] = False
    finally:
        overall_elapsed = time.perf_counter() - overall_start
        report["elapsed_seconds"] = round(overall_elapsed, 4)
        report["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n[REPORT] Saved smoke test report to {report_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Docling Serve Smoke Test Runner")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base API URL")
    parser.add_argument("--sample-url", default=DEFAULT_SAMPLE_URL, help="Document URL to convert")
    parser.add_argument("--timeout", type=float, default=300.0, help="Max wait seconds for conversion")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Polling interval in seconds")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Path to write JSON report")

    args = parser.parse_args()
    report = run_smoke_test(
        base_url=args.base_url,
        sample_url=args.sample_url,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        report_path=Path(args.report),
    )

    if not report["success"]:
        sys.exit(1)
    print("Smoke test passed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()

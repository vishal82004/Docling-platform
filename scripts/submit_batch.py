#!/usr/bin/env python3
"""
Repeatable batch load generator for Docling Serve asynchronous conversion.
Measures throughput (jobs/min), p50/p95 latency, queue depth, error rates,
and captures container resource stats for worker scaling comparisons.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add script directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from client import DoclingClient

DEFAULT_BASE_URL = os.environ.get("DOCLING_BASE_URL", "http://127.0.0.1:5001")
DEFAULT_SAMPLES = [
    "https://arxiv.org/pdf/2501.17887",
]


def get_redis_queue_length() -> Optional[int]:
    """Fetch current length of rq:queue:convert via docker compose exec redis."""
    try:
        cmd = ["docker", "compose", "exec", "-T", "redis", "redis-cli", "LLEN", "rq:queue:convert"]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=5).decode().strip()
        return int(out)
    except Exception:
        return None


def get_docker_stats() -> List[Dict[str, Any]]:
    """Capture current CPU and memory stats for docker containers."""
    try:
        cmd = [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}|{{.NetIO}}|{{.BlockIO}}",
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=10).decode().strip()
        stats = []
        for line in out.splitlines():
            parts = line.strip().split("|")
            if len(parts) >= 6:
                stats.append(
                    {
                        "name": parts[0],
                        "cpu_percent": parts[1],
                        "mem_usage": parts[2],
                        "mem_percent": parts[3],
                        "net_io": parts[4],
                        "block_io": parts[5],
                    }
                )
        return stats
    except Exception:
        return []


def calculate_percentiles(values: List[float]) -> Dict[str, float]:
    """Calculate p50, p95, min, max, avg for a list of floats."""
    if not values:
        return {"min": 0.0, "max": 0.0, "avg": 0.0, "p50": 0.0, "p95": 0.0}
    sorted_vals = sorted(values)
    n = len(sorted_vals)

    def percentile(p: float) -> float:
        if n == 1:
            return sorted_vals[0]
        k = (n - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        d0 = sorted_vals[int(f)] * (c - k)
        d1 = sorted_vals[int(c)] * (k - f)
        return d0 + d1

    return {
        "min": round(sorted_vals[0], 3),
        "max": round(sorted_vals[-1], 3),
        "avg": round(sum(sorted_vals) / n, 3),
        "p50": round(percentile(0.50), 3),
        "p95": round(percentile(0.95), 3),
    }


def process_single_job(
    client: DoclingClient, job_index: int, sample_url: str, timeout: float, poll_interval: float
) -> Dict[str, Any]:
    """Submit a single async job and poll until completion."""
    submit_start = time.perf_counter()
    submitted_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record: Dict[str, Any] = {
        "job_index": job_index,
        "sample_url": sample_url,
        "submitted_at": submitted_at,
        "task_id": None,
        "status": "submission_failed",
        "error": None,
        "submit_latency_sec": 0.0,
        "poll_duration_sec": 0.0,
        "total_latency_sec": 0.0,
    }

    try:
        payload = client.build_url_payload(sample_url, to_formats=["md"])
        t0 = time.perf_counter()
        resp = client.submit_async(payload)
        t1 = time.perf_counter()

        record["submit_latency_sec"] = round(t1 - t0, 4)
        task_id = resp["task_id"]
        record["task_id"] = task_id
        record["initial_status"] = resp.get("task_status")

        # Poll
        t_poll_start = time.perf_counter()
        status_res = client.wait_for_completion(
            task_id=task_id, timeout=timeout, poll_interval=poll_interval, fail_on_error=False
        )
        t_poll_end = time.perf_counter()
        record["poll_duration_sec"] = round(t_poll_end - t_poll_start, 4)
        record["total_latency_sec"] = round(time.perf_counter() - submit_start, 4)
        record["status"] = status_res.get("task_status", "unknown")
        record["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if record["status"] != "success":
            record["error"] = status_res.get("error_message") or f"Terminal status: {record['status']}"

    except Exception as exc:
        record["total_latency_sec"] = round(time.perf_counter() - submit_start, 4)
        record["error"] = str(exc)
        record["status"] = "error"
        record["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return record


def run_batch(
    total_jobs: int = 5,
    concurrency: int = 2,
    base_url: str = DEFAULT_BASE_URL,
    sample_urls: Optional[List[str]] = None,
    worker_label: str = "current-workers",
    timeout: float = 300.0,
    poll_interval: float = 2.0,
    max_consecutive_failures: int = 3,
    report_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute batch test, track metrics and write reports."""
    client = DoclingClient(base_url=base_url)
    samples = sample_urls or DEFAULT_SAMPLES

    print("=" * 65)
    print(f"Starting Batch Load Generator: {total_jobs} jobs | concurrency {concurrency} | label: {worker_label}")
    print("=" * 65)

    initial_stats = get_docker_stats()
    initial_queue_len = get_redis_queue_length()

    batch_start_wall = datetime.datetime.now(datetime.timezone.utc)
    t_start = time.perf_counter()

    results: List[Dict[str, Any]] = []
    consecutive_failures = 0
    circuit_broken = False

    # Submit and monitor with a thread pool
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {}
        for i in range(1, total_jobs + 1):
            if consecutive_failures >= max_consecutive_failures:
                print(
                    f"[CIRCUIT BREAKER] {consecutive_failures} consecutive failures. Stopping further job submissions."
                )
                circuit_broken = True
                break

            url = samples[(i - 1) % len(samples)]
            fut = executor.submit(process_single_job, client, i, url, timeout, poll_interval)
            futures[fut] = i
            print(f"-> Scheduled job {i}/{total_jobs}")

        for fut in concurrent.futures.as_completed(futures):
            job_idx = futures[fut]
            res = fut.result()
            results.append(res)
            status = res["status"]
            dur = res["total_latency_sec"]

            if status == "success":
                consecutive_failures = 0
                print(f"<- [Job {job_idx:02d}] SUCCESS in {dur:.2f}s (Task ID: {res['task_id']})")
            else:
                consecutive_failures += 1
                print(f"<- [Job {job_idx:02d}] FAILED ({status}) in {dur:.2f}s: {res.get('error')}")

    t_end = time.perf_counter()
    total_elapsed_sec = t_end - t_start
    final_stats = get_docker_stats()
    final_queue_len = get_redis_queue_length()

    # Aggregate metrics
    completed = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]
    total_submitted = len(results)
    success_count = len(completed)
    failure_count = len(failed)

    success_latencies = [r["total_latency_sec"] for r in completed]
    percentiles = calculate_percentiles(success_latencies)
    jobs_per_minute = round((success_count / total_elapsed_sec) * 60.0, 2) if total_elapsed_sec > 0 else 0.0

    report: Dict[str, Any] = {
        "worker_label": worker_label,
        "batch_start": batch_start_wall.isoformat(),
        "batch_end": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_jobs_requested": total_jobs,
        "total_jobs_submitted": total_submitted,
        "concurrency": concurrency,
        "circuit_broken": circuit_broken,
        "elapsed_seconds": round(total_elapsed_sec, 2),
        "jobs_per_minute": jobs_per_minute,
        "summary": {
            "submitted": total_submitted,
            "succeeded": success_count,
            "failed": failure_count,
            "success_rate_percent": round((success_count / total_submitted) * 100.0, 1) if total_submitted else 0.0,
            "latency_percentiles_sec": percentiles,
        },
        "queue": {"initial_depth": initial_queue_len, "final_depth": final_queue_len},
        "docker_stats": {"initial": initial_stats, "final": final_stats},
        "jobs": results,
    }

    # Print summary
    print("\n" + "=" * 65)
    print(f"BATCH SUMMARY — {worker_label}")
    print("=" * 65)
    print(f"Total Submitted:     {total_submitted}/{total_jobs}")
    print(f"Succeeded:           {success_count}")
    print(f"Failed:              {failure_count}")
    print(f"Total Wall Time:     {total_elapsed_sec:.2f} seconds")
    print(f"Throughput:          {jobs_per_minute} jobs/minute")
    print(f"Completion p50:      {percentiles['p50']}s")
    print(f"Completion p95:      {percentiles['p95']}s")
    print(f"Completion Min/Max:  {percentiles['min']}s / {percentiles['max']}s")
    print(f"Queue Depth End:     {final_queue_len}")
    print("=" * 65)

    if report_file:
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Saved batch report to {report_file}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Docling Serve Batch Load Runner")
    parser.add_argument("-n", "--jobs", type=int, default=5, help="Total number of jobs to run")
    parser.add_argument("-c", "--concurrency", type=int, default=2, help="Concurrency limit for in-flight jobs")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base API URL")
    parser.add_argument(
        "--worker-label", default="default-workers", help="Worker label for test run (e.g. 1-worker, 2-workers)"
    )
    parser.add_argument("--timeout", type=float, default=300.0, help="Per-job timeout in seconds")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Poll interval in seconds")
    parser.add_argument(
        "--max-failures", type=int, default=3, help="Max consecutive failures before circuit breaker stops test"
    )
    parser.add_argument("--report", default=None, help="Output path for JSON report")

    args = parser.parse_args()

    report_path = Path(args.report) if args.report else PROJECT_ROOT / "reports" / f"batch-{args.worker_label}.json"

    run_batch(
        total_jobs=args.jobs,
        concurrency=args.concurrency,
        base_url=args.base_url,
        worker_label=args.worker_label,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        max_consecutive_failures=args.max_failures,
        report_file=report_path,
    )


if __name__ == "__main__":
    main()

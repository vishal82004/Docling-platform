#!/usr/bin/env python3
"""
Local Event-Driven Autoscaler for Docker Compose.
Simulates KEDA's exact behavior by monitoring `rq:queue:convert` in Redis
and dynamically scaling `docling-worker` containers via `docker compose up -d --scale`.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import time

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def get_queue_depth() -> int:
    """Fetch current length of rq:queue:convert from Redis container."""
    try:
        cmd = ["docker", "compose", "exec", "-T", "redis", "redis-cli", "LLEN", "rq:queue:convert"]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=4).decode().strip()
        return int(out)
    except Exception:
        return 0


def get_active_workers() -> int:
    """Count running docling-worker containers."""
    try:
        cmd = ["docker", "compose", "ps", "docling-worker", "--format", "{{.Name}}"]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=4).decode().strip()
        lines = [line for line in out.splitlines() if line.strip()]
        return max(1, len(lines))
    except Exception:
        return 1


def scale_workers(count: int) -> bool:
    """Scale docling-worker to desired replica count via Docker Compose."""
    try:
        cmd = ["docker", "compose", "up", "-d", "--scale", f"docling-worker={count}"]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        return True
    except Exception as e:
        print(f"[AUTOSCALER ERROR] Failed to scale to {count}: {e}")
        return False


def run_autoscaler(
    min_workers: int = 1,
    max_workers: int = 3,
    jobs_per_worker: int = 2,
    cooldown_seconds: int = 30,
    poll_interval: float = 3.0,
):
    """Event-driven scaling loop mirroring KEDA ScaledObject semantics."""
    print("=" * 68)
    print("🚀 LOCAL EVENT-DRIVEN AUTOSCALER (KEDA SIMULATOR)")
    print("=" * 68)
    print("Target Queue:     rq:queue:convert")
    print(f"Trigger Target:   {jobs_per_worker} jobs / worker (KEDA listLength: {jobs_per_worker})")
    print(f"Worker Capacity:  Min={min_workers} | Max={max_workers}")
    print(f"Cooldown Window:  {cooldown_seconds}s (before scale-down)")
    print(f"Poll Interval:    {poll_interval}s")
    print("=" * 68)
    print("Press CTRL+C to stop the autoscaler.\n")

    current_workers = get_active_workers()
    idle_start_time = None

    try:
        while True:
            queue_len = get_queue_depth()

            # Calculate desired workers based on queue depth
            if queue_len > 0:
                idle_start_time = None
                # Formula: ceil(queue_length / jobs_per_worker)
                needed = math.ceil(queue_len / jobs_per_worker)
                desired_workers = max(min_workers, min(max_workers, needed))
            else:
                if idle_start_time is None:
                    idle_start_time = time.time()
                idle_duration = time.time() - idle_start_time

                if idle_duration >= cooldown_seconds:
                    desired_workers = min_workers
                else:
                    desired_workers = current_workers

            # Check if scaling action is required
            if desired_workers > current_workers:
                print(
                    f"⚡ [SCALE UP] Queue depth={queue_len} -> Scaling workers from {current_workers} to {desired_workers}..."
                )
                if scale_workers(desired_workers):
                    current_workers = desired_workers
                    print(f"   ✓ Scale up complete! Active workers: {current_workers}")

            elif desired_workers < current_workers and (time.time() - idle_start_time) >= cooldown_seconds:
                print(
                    f"💤 [SCALE DOWN] Queue empty for {int(time.time() - idle_start_time)}s -> Scaling back to {desired_workers} worker(s)..."
                )
                if scale_workers(desired_workers):
                    current_workers = desired_workers
                    print(f"   ✓ Scale down complete! Active workers: {current_workers}")

            # Heartbeat display
            idle_info = f" (Idle {int(time.time() - idle_start_time)}s)" if idle_start_time and queue_len == 0 else ""
            sys.stdout.write(
                f"\r[STATUS] Queue Backlog: {queue_len:2d} | Active Workers: {current_workers}/{max_workers}{idle_info}   "
            )
            sys.stdout.flush()

            time.sleep(poll_interval)

    except KeyboardInterrupt:
        print("\n\nStopping local autoscaler. Scaling back to default 1 worker...")
        scale_workers(min_workers)
        print("Done.")


def main():
    parser = argparse.ArgumentParser(description="Local KEDA Autoscaling Simulator for Docker Compose")
    parser.add_argument("--min", type=int, default=1, help="Minimum workers (warm base)")
    parser.add_argument("--max", type=int, default=3, help="Maximum workers to scale up to")
    parser.add_argument("--jobs-per-worker", type=int, default=2, help="KEDA listLength threshold")
    parser.add_argument("--cooldown", type=int, default=20, help="Cooldown window in seconds before scaling down")
    parser.add_argument("--interval", type=float, default=3.0, help="Polling interval in seconds")

    args = parser.parse_args()
    run_autoscaler(
        min_workers=args.min,
        max_workers=args.max,
        jobs_per_worker=args.jobs_per_worker,
        cooldown_seconds=args.cooldown,
        poll_interval=args.interval,
    )


if __name__ == "__main__":
    main()

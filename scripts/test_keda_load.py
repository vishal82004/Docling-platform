import concurrent.futures
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client import DoclingClient


def main():
    client = DoclingClient("http://127.0.0.1:5001")
    payload = client.build_url_payload("https://arxiv.org/pdf/2501.17887")

    print("Submitting 6 async conversion jobs to trigger KEDA autoscaling...")

    def submit(i):
        res = client.submit_async(payload)
        task_id = res.get("task_id")
        print(f"[{i}] Submitted job: {task_id}")
        return task_id

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        task_ids = list(executor.map(submit, range(1, 7)))

    print(f"Successfully enqueued {len(task_ids)} jobs in {time.time() - start:.2f}s!")


if __name__ == "__main__":
    main()

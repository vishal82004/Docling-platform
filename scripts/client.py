"""Client wrapper for Docling Serve API."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

TERMINAL_STATUSES = {"success", "failure", "partial_success", "skipped"}
NON_TERMINAL_STATUSES = {"pending", "started"}


class DoclingClientError(Exception):
    """Base exception for Docling client operations."""

    pass


class TaskFailedError(DoclingClientError):
    """Raised when a task reaches a failed terminal state."""

    pass


class TaskTimeoutError(DoclingClientError):
    """Raised when polling exceeds the configured deadline."""

    pass


class DoclingClient:
    """HTTP client communicating with Docling Serve REST API."""

    def __init__(self, base_url: str = "http://127.0.0.1:5001", session: Optional[requests.Session] = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def health(self, timeout: float = 10.0) -> Dict[str, Any]:
        """Check API health status."""
        resp = self.session.get(f"{self.base_url}/health", timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def ready(self, timeout: float = 10.0) -> Dict[str, Any]:
        """Check API readiness status."""
        resp = self.session.get(f"{self.base_url}/ready", timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def build_url_payload(urls: List[str] | str, to_formats: Optional[List[str]] = None) -> Dict[str, Any]:
        """Construct the standard async conversion payload."""
        if isinstance(urls, str):
            urls = [urls]
        if to_formats is None:
            to_formats = ["md"]
        return {"sources": [{"kind": "http", "url": u} for u in urls], "options": {"to_formats": to_formats}}

    def submit_async(self, payload: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """Submit an asynchronous conversion job."""
        url = f"{self.base_url}/v1/convert/source/async"
        resp = self.session.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("task_id"):
            raise DoclingClientError(f"No task_id returned in response: {data}")
        return data

    def poll_status(self, task_id: str, timeout: float = 15.0) -> Dict[str, Any]:
        """Poll task status once."""
        url = f"{self.base_url}/v1/status/poll/{task_id}"
        resp = self.session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def wait_for_completion(
        self, task_id: str, timeout: float = 300.0, poll_interval: float = 2.0, fail_on_error: bool = False
    ) -> Dict[str, Any]:
        """
        Poll task until terminal state or timeout.
        Returns final status dictionary.
        """
        deadline = time.time() + timeout
        start_time = time.time()
        last_status = None

        while time.time() < deadline:
            status_data = self.poll_status(task_id)
            status = status_data.get("task_status")
            last_status = status_data

            if status in TERMINAL_STATUSES:
                if status != "success" and fail_on_error:
                    msg = status_data.get("error_message") or f"Task {task_id} failed with status {status}"
                    raise TaskFailedError(msg)
                return status_data

            time.sleep(poll_interval)

        elapsed = time.time() - start_time
        raise TaskTimeoutError(
            f"Task {task_id} did not complete within {timeout}s (elapsed: {elapsed:.2f}s, last status: {last_status})"
        )

    def get_result(self, task_id: str, timeout: float = 60.0) -> Dict[str, Any]:
        """Fetch converted result for a completed task."""
        url = f"{self.base_url}/v1/result/{task_id}"
        resp = self.session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

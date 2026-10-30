"""Integration tests for Docling API (runs against live service)."""

from __future__ import annotations

import os

import pytest
import requests

from scripts.client import DoclingClient

BASE_URL = os.environ.get("DOCLING_BASE_URL", "http://127.0.0.1:5001")
SAMPLE_URL = "https://arxiv.org/pdf/2501.17887"


@pytest.fixture(scope="module")
def client():
    return DoclingClient(base_url=BASE_URL)


@pytest.mark.integration
def test_live_health_endpoint(client):
    """Verify live Docling service responds to health check."""
    resp = client.health()
    assert isinstance(resp, dict)
    assert resp.get("status") == "ok"


@pytest.mark.integration
def test_live_ready_endpoint(client):
    """Verify live Docling service responds to ready check."""
    resp = client.ready()
    assert isinstance(resp, dict)
    assert resp.get("status") == "ok"


@pytest.mark.integration
def test_live_malformed_request_error(client):
    """Verify malformed requests return HTTP 422 Unprocessable Entity."""
    # Empty sources list violates minItems: 1 constraint
    bad_payload = {"sources": [], "options": {"to_formats": ["md"]}}
    with pytest.raises(requests.HTTPError) as exc_info:
        client.submit_async(bad_payload)
    assert exc_info.value.response.status_code == 422


@pytest.mark.integration
def test_live_submit_and_poll_conversion(client):
    """Submit a real async conversion job and verify it reaches success state."""
    payload = client.build_url_payload(SAMPLE_URL, to_formats=["md"])
    sub_res = client.submit_async(payload)
    task_id = sub_res["task_id"]
    assert task_id is not None
    assert sub_res.get("task_status") in {"pending", "started"}

    status_data = client.wait_for_completion(task_id, timeout=180.0, poll_interval=2.0)
    assert status_data["task_status"] == "success"

    # Verify result endpoint
    result = client.get_result(task_id)
    assert isinstance(result, dict)

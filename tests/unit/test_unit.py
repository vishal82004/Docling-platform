"""Unit tests for Docling client and conversion lifecycle (no service required)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import requests

from scripts.client import (
    DoclingClient,
    DoclingClientError,
    TaskFailedError,
    TaskTimeoutError,
)


class TestDoclingClientUnit(unittest.TestCase):
    """Unit tests validating client behavior in isolation with mocked HTTP responses."""

    def setUp(self):
        self.client = DoclingClient(base_url="http://mock-docling:5001")

    def test_build_url_payload_single_and_list(self):
        """Test payload construction conforms to OpenAPI schema."""
        # Single string URL
        p1 = self.client.build_url_payload("https://example.com/doc.pdf")
        self.assertEqual(
            p1, {"sources": [{"kind": "http", "url": "https://example.com/doc.pdf"}], "options": {"to_formats": ["md"]}}
        )

        # List of URLs with custom formats
        p2 = self.client.build_url_payload(
            ["https://example.com/1.pdf", "https://example.com/2.pdf"], to_formats=["md", "json"]
        )
        self.assertEqual(len(p2["sources"]), 2)
        self.assertEqual(p2["options"]["to_formats"], ["md", "json"])

    @patch("requests.Session.get")
    def test_health_endpoint_success(self, mock_get):
        """Verify health check returns expected status dict on 200."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_resp

        res = self.client.health()
        self.assertEqual(res, {"status": "ok"})
        mock_get.assert_called_once_with("http://mock-docling:5001/health", timeout=10.0)

    @patch("requests.Session.post")
    def test_submission_of_known_good_sample(self, mock_post):
        """Verify successful async submission returns task_id."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"task_id": "test-task-1234", "task_type": "convert", "task_status": "pending"}
        mock_post.return_value = mock_resp

        payload = self.client.build_url_payload("https://example.com/doc.pdf")
        res = self.client.submit_async(payload)

        self.assertEqual(res["task_id"], "test-task-1234")
        self.assertEqual(res["task_status"], "pending")
        mock_post.assert_called_once_with(
            "http://mock-docling:5001/v1/convert/source/async", json=payload, timeout=30.0
        )

    @patch("requests.Session.post")
    def test_malformed_request_returns_controlled_error(self, mock_post):
        """Verify 422 HTTP response or missing task_id raises controlled error."""
        # Case A: HTTP 422 Unprocessable Entity
        mock_resp_422 = MagicMock()
        mock_resp_422.status_code = 422
        mock_resp_422.raise_for_status.side_effect = requests.HTTPError("422 Client Error: Unprocessable Entity")
        mock_post.return_value = mock_resp_422

        with self.assertRaises(requests.HTTPError):
            self.client.submit_async({"sources": []})

        # Case B: 200 response missing task_id
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.raise_for_status.return_value = None
        mock_resp_200.json.return_value = {"error": "no id"}
        mock_post.return_value = mock_resp_200

        with self.assertRaises(DoclingClientError) as ctx:
            self.client.submit_async({"sources": []})
        self.assertIn("No task_id returned", str(ctx.exception))

    @patch("scripts.client.DoclingClient.poll_status")
    def test_status_polling_handles_non_terminal_state(self, mock_poll):
        """Verify polling continues through 'pending' and 'started' before returning on 'success'."""
        mock_poll.side_effect = [
            {"task_id": "t1", "task_status": "pending"},
            {"task_id": "t1", "task_status": "started"},
            {"task_id": "t1", "task_status": "success"},
        ]

        with patch("time.sleep", return_value=None):
            result = self.client.wait_for_completion("t1", timeout=10.0, poll_interval=0.1)

        self.assertEqual(result["task_status"], "success")
        self.assertEqual(mock_poll.call_count, 3)

    @patch("scripts.client.DoclingClient.poll_status")
    def test_polling_stops_at_timeout_instead_of_looping_forever(self, mock_poll):
        """Verify polling terminates and raises TaskTimeoutError when deadline passes."""
        mock_poll.return_value = {"task_id": "t-slow", "task_status": "pending"}

        # Simulate timeout by letting elapsed time exceed timeout
        with patch("time.time", side_effect=[100.0, 100.5, 105.0, 110.0, 115.0]):
            with patch("time.sleep", return_value=None):
                with self.assertRaises(TaskTimeoutError) as ctx:
                    self.client.wait_for_completion("t-slow", timeout=5.0, poll_interval=1.0)
                self.assertIn("did not complete within 5.0s", str(ctx.exception))

    @patch("scripts.client.DoclingClient.poll_status")
    def test_failed_task_not_counted_as_successful(self, mock_poll):
        """Verify task status 'failure' is correctly identified and not reported as success."""
        mock_poll.return_value = {
            "task_id": "t-fail",
            "task_status": "failure",
            "error_message": "Document conversion crashed: Out of memory",
        }

        # Subtest 1: fail_on_error=True raises TaskFailedError
        with self.assertRaises(TaskFailedError) as ctx:
            self.client.wait_for_completion("t-fail", timeout=10.0, fail_on_error=True)
        self.assertIn("Out of memory", str(ctx.exception))

        # Subtest 2: fail_on_error=False returns failure dict, status is distinctly NOT 'success'
        res = self.client.wait_for_completion("t-fail", timeout=10.0, fail_on_error=False)
        self.assertEqual(res["task_status"], "failure")
        self.assertNotEqual(res["task_status"], "success")


class TestOpenTelemetryTelemetry(unittest.TestCase):
    """Unit tests validating OpenTelemetry tracer initialization and span context manager."""

    def test_trace_span_context_manager(self):
        """Verify trace_span creates a span and records attributes without throwing exceptions."""
        from monitoring.telemetry import get_tracer, trace_span

        tracer = get_tracer()
        self.assertIsNotNone(tracer)

        # Normal execution
        with trace_span("unit_test_span", {"test.attr": "value", "count": 42}) as span:
            self.assertIsNotNone(span)

        # Exception handling inside span
        with self.assertRaises(ValueError):
            with trace_span("failing_test_span", {"error.test": True}):
                raise ValueError("Expected test error")


if __name__ == "__main__":
    unittest.main()

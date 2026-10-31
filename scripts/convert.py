#!/usr/bin/env python3
"""
Convert documents (URLs or local files) via Docling Serve API
and instrument the conversion with MLflow Tracing for real-time observability.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"

# Add script directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from client import DoclingClient

try:
    import mlflow

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False


def resolve_mlflow_tracking_uri(explicit_uri: Optional[str] = None) -> Optional[str]:
    """Resolve MLflow tracking URI: CLI argument > env var > reachable local container > None."""
    if explicit_uri:
        return explicit_uri
    if os.environ.get("MLFLOW_TRACKING_URI"):
        return os.environ["MLFLOW_TRACKING_URI"]
    try:
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:5000/health", timeout=0.5) as resp:
            if resp.status == 200:
                return "http://127.0.0.1:5000"
    except Exception:
        pass
    return None


def convert_document(
    source: str,
    base_url: str = "http://127.0.0.1:5001",
    target_format: str = "md",
    output_path: Optional[Path] = None,
    experiment_name: str = "docling-live-conversions",
    tracking_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convert a document via Docling Serve, track the span in MLflow Traces,
    and optionally save the converted output to disk.
    """
    client = DoclingClient(base_url=base_url)
    is_url = source.startswith("http://") or source.startswith("https://")
    source_type = "url" if is_url else "file"

    # Setup MLflow Tracking
    mlflow_active = False
    resolved_uri = resolve_mlflow_tracking_uri(tracking_uri)
    if MLFLOW_AVAILABLE and resolved_uri:
        try:
            mlflow.set_tracking_uri(resolved_uri)
            mlflow.set_experiment(experiment_name)
            mlflow_active = True
        except Exception as e:
            print(f"[MLflow WARN] Failed to connect to MLflow: {e}")

    print("=" * 68)
    print("DOCLING ASYNC DOCUMENT CONVERSION")
    print("=" * 68)
    print(f"Source:         {source}")
    print(f"Source Type:    {source_type.upper()}")
    print(f"Target Format:  {target_format}")
    print(f"Docling API:    {base_url}")
    if mlflow_active:
        print(f"MLflow Tracing: Active at {resolved_uri} (Experiment: {experiment_name})")
    print("-" * 68)

    t0 = time.perf_counter()
    trace_id = None

    if mlflow_active and hasattr(mlflow, "start_span"):
        try:
            with mlflow.start_span(name="docling_convert_document") as span:
                span.set_inputs(
                    {
                        "source": source,
                        "source_type": source_type,
                        "target_format": target_format,
                        "base_url": base_url,
                    }
                )
                print("-> Submitting conversion job...")
                conversion_result = client.convert(source=source, to_formats=[target_format])
                elapsed = time.perf_counter() - t0

                task_id = conversion_result["task_id"]
                raw_doc = conversion_result["result"].get("document", {})
                converted_content = (
                    raw_doc.get(f"{target_format}_content")
                    or raw_doc.get("md_content")
                    or raw_doc.get("text_content")
                    or ""
                )

                span.set_outputs(
                    {
                        "task_id": task_id,
                        "status": "SUCCESS",
                        "latency_seconds": round(elapsed, 2),
                        "filename": raw_doc.get("filename", Path(source).name if not is_url else source),
                        "content_length": len(converted_content),
                        "preview": converted_content[:500] if converted_content else "",
                    }
                )
                trace_id = span.request_id if hasattr(span, "request_id") else None
        except Exception as span_err:
            print(f"[MLflow WARN] Tracing error: {span_err}")
            conversion_result = client.convert(source=source, to_formats=[target_format])
            elapsed = time.perf_counter() - t0
    else:
        print("-> Submitting conversion job...")
        conversion_result = client.convert(source=source, to_formats=[target_format])
        elapsed = time.perf_counter() - t0

    task_id = conversion_result["task_id"]
    raw_doc = conversion_result["result"].get("document", {})
    converted_content = (
        raw_doc.get(f"{target_format}_content") or raw_doc.get("md_content") or raw_doc.get("text_content") or ""
    )

    print("<- [SUCCESS] Conversion completed!")
    print(f"Task ID:        {task_id}")
    print(f"Total Time:     {elapsed:.2f} seconds")
    print(f"Content Length: {len(converted_content):,} characters")

    # Save output if requested
    if output_path and converted_content:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(converted_content)
        print(f"Saved Output:   {output_path}")

    # Display preview
    if converted_content:
        print("\n" + "=" * 68)
        print("CONVERTED PREVIEW (First 400 characters):")
        print("=" * 68)
        preview_text = converted_content[:400].strip()
        print(preview_text)
        if len(converted_content) > 400:
            print("\n... [truncated] ...")
        print("=" * 68)

    # MLflow link
    if mlflow_active:
        print(f"\n[MLflow] Trace logged to experiment '{experiment_name}'!")
        if trace_id:
            print(f"  -> Trace Request ID: {trace_id}")
        print(f"  -> Open Traces Dashboard: {resolved_uri}/#/experiments")
        print("     (Click 'Traces' tab at the top to inspect this conversion)")

    return conversion_result


def main():
    parser = argparse.ArgumentParser(description="Convert documents with Docling & MLflow Tracing")
    parser.add_argument(
        "source",
        nargs="?",
        default="https://arxiv.org/pdf/2501.17887",
        help="URL or local file path to convert (defaults to Docling paper PDF)",
    )
    parser.add_argument("--format", default="md", choices=["md", "json", "html", "text"], help="Target format")
    parser.add_argument("--output", "-o", default=None, help="Optional output file path to save converted content")
    parser.add_argument("--base-url", default="http://127.0.0.1:5001", help="Docling Serve API base URL")
    parser.add_argument(
        "--experiment-name", default="docling-live-conversions", help="MLflow experiment name for conversions"
    )
    parser.add_argument("--tracking-uri", default=None, help="MLflow tracking URI")

    args = parser.parse_args()
    out_path = Path(args.output) if args.output else None

    convert_document(
        source=args.source,
        base_url=args.base_url,
        target_format=args.format,
        output_path=out_path,
        experiment_name=args.experiment_name,
        tracking_uri=args.tracking_uri,
    )


if __name__ == "__main__":
    main()

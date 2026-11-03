#!/usr/bin/env python3
"""
End-to-End Document Intelligence Pipeline:
Combines Docling Serve (Document Parsing & OCR) with vLLM (Structured LLM Entity Extraction)
into a unified, distributed-traced workflow.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from client import DoclingClient
from vllm_client import InvoiceExtraction, VLLMClient

try:
    from monitoring.telemetry import trace_span
except Exception:
    from contextlib import contextmanager

    @contextmanager
    def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None):
        yield None


def run_pipeline(
    source: str,
    docling_base_url: str = "http://127.0.0.1:5001",
    vllm_base_url: str = "http://127.0.0.1:8000/v1",
    vllm_model: str = "Qwen/Qwen2.5-0.5B-Instruct",
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute end-to-end document conversion + LLM entity extraction."""
    print("=" * 72)
    print("DOCUMENT INTELLIGENCE PIPELINE (Docling + vLLM)")
    print("=" * 72)
    print(f"Source Document:  {source}")
    print(f"Docling Serve:    {docling_base_url}")
    print(f"vLLM Engine:      {vllm_base_url} (Model: {vllm_model})")
    print("-" * 72)

    total_start = time.perf_counter()

    with trace_span("document_intelligence_pipeline", {"pipeline.source": source}) as root_span:
        # -----------------------------------------------------------------
        # Stage 1: Docling Document Conversion & OCR
        # -----------------------------------------------------------------
        print("-> [Stage 1/2] Converting document with Docling Serve...")
        t0 = time.perf_counter()
        docling_client = DoclingClient(base_url=docling_base_url)
        source_path = Path(source)
        task_id = "local-pass-through"
        markdown_content = ""

        try:
            docling_res = docling_client.convert(source=source, to_formats=["md"])
            task_id = docling_res.get("task_id", "unknown")
            raw_doc = docling_res.get("result", {}).get("document", {})
            markdown_content = raw_doc.get("md_content") or raw_doc.get("text_content") or ""
        except Exception as e:
            if source_path.exists() and source_path.suffix.lower() == ".md":
                print(f"   (Docling Serve at {docling_base_url} unavailable: {e}. Reading local markdown directly.)")
                with open(source_path, "r", encoding="utf-8") as f:
                    markdown_content = f.read()
                task_id = f"local-{source_path.stem}"
            else:
                raise

        docling_elapsed = time.perf_counter() - t0

        print(f"   [+] Docling Conversion Complete ({docling_elapsed:.2f}s) | Task ID: {task_id}")
        print(f"   [+] Markdown Content Length: {len(markdown_content):,} characters")

        if root_span:
            root_span.set_attribute("docling.task_id", task_id)
            root_span.set_attribute("docling.duration_seconds", round(docling_elapsed, 4))

        # -----------------------------------------------------------------
        # Stage 2: vLLM Structured Entity Extraction
        # -----------------------------------------------------------------
        print("-> [Stage 2/2] Extracting structured entities with vLLM...")
        t1 = time.perf_counter()
        vllm_client = VLLMClient(base_url=vllm_base_url, model=vllm_model)
        extraction: InvoiceExtraction = vllm_client.extract_from_markdown(markdown_content)
        vllm_elapsed = time.perf_counter() - t1
        overall_elapsed = time.perf_counter() - total_start

        print(f"   [+] vLLM Extraction Complete ({vllm_elapsed:.2f}s)")
        print(f"   [+] Vendor:         {extraction.vendor}")
        print(f"   [+] Invoice Number: {extraction.invoice_number}")
        print(f"   [+] Invoice Date:   {extraction.invoice_date}")
        print(f"   [+] Total Amount:   ${extraction.total:,.2f}" if extraction.total else "   [+] Total: N/A")

        if root_span:
            root_span.set_attribute("vllm.duration_seconds", round(vllm_elapsed, 4))
            root_span.set_attribute("pipeline.total_seconds", round(overall_elapsed, 4))

        result_payload = {
            "source": source,
            "status": "success",
            "task_id": task_id,
            "timing": {
                "docling_seconds": round(docling_elapsed, 4),
                "vllm_seconds": round(vllm_elapsed, 4),
                "total_seconds": round(overall_elapsed, 4),
            },
            "entities": extraction.model_dump(),
            "markdown_preview": markdown_content[:500] if markdown_content else "",
        }

        # Save to output file if requested
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result_payload, f, indent=2)
            print(f"\n[OUTPUT] Saved structured pipeline result to {output_path}")

        print("=" * 72)
        print(f"PIPELINE COMPLETED SUCCESSFULLY in {overall_elapsed:.2f} seconds")
        print("  -> View distributed trace in Jaeger: http://localhost:16686")
        print("=" * 72)

        return result_payload


def main():
    parser = argparse.ArgumentParser(description="End-to-End Document Intelligence Pipeline (Docling + vLLM)")
    parser.add_argument(
        "source",
        nargs="?",
        default="evaluation/dataset/invoice-eval-v1/documents/inv_001.md",
        help="Path or URL of the document to convert & extract",
    )
    parser.add_argument("--docling-url", default="http://127.0.0.1:5001", help="Docling Serve base URL")
    parser.add_argument("--vllm-url", default="http://127.0.0.1:8000/v1", help="vLLM OpenAI-compatible base URL")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct", help="Model name on vLLM server")
    parser.add_argument("-o", "--output", default=None, help="Path to write output JSON")

    args = parser.parse_args()
    out_path = Path(args.output) if args.output else None

    run_pipeline(
        source=args.source,
        docling_base_url=args.docling_url,
        vllm_base_url=args.vllm_url,
        vllm_model=args.model,
        output_path=out_path,
    )


if __name__ == "__main__":
    main()

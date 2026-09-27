"""Basic local smoke entrypoint for TIL parser/chunker/embedder contracts.

This is intentionally lightweight and job-free. It validates wiring only.
Usage example:
  python validation/tils/nb_til_smoke.py --pdf /path/to/sample.pdf
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from contracts.types.entities import DocumentReference
from common.parsers import DatabricksAIParser
from gold.src.tils.chunkers import RecursiveTextChunker
from gold.src.tils.embedders import LiteLLMEmbedder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TIL basic smoke test (no jobs).")
    parser.add_argument("--pdf", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_path = args.pdf
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    payload = pdf_path.read_bytes()
    doc_ref = DocumentReference(
        document_id=pdf_path.stem,
        source_path=str(pdf_path),
        source_hash=hashlib.sha1(payload).hexdigest(),
    )

    parser = DatabricksAIParser()
    chunker = RecursiveTextChunker()
    embedder = LiteLLMEmbedder(model_name="replace-me")

    profile = parser.parse(doc_ref, payload)
    chunks = chunker.chunk(profile)
    vectors = embedder.embed(chunks)

    print({
        "document_id": doc_ref.document_id,
        "chunk_count": len(chunks),
        "vector_count": len(vectors),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Document Loading – Databricks
Loads chunk rows from EMBEDDINGS_TABLE (Delta), the single source of truth for
the cleaned pipeline package.
"""
from typing import List, Tuple

from langchain_core.documents import Document

from config import EMBEDDINGS_TABLE
from utils import setup_logger, clean_metadata

logger = setup_logger("document_loader")


def load_all_chunks_from_delta() -> Tuple[List[Document], dict]:
    """
    Load all rows from EMBEDDINGS_TABLE ordered by (pdf_name, page_number).
    Returns text plus minimal metadata for inspection.
    Returns (documents, stats).
    """
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()

    logger.info(f"Loading chunks from: {EMBEDDINGS_TABLE}")

    try:
        df = (spark.table(EMBEDDINGS_TABLE)
              .select("pdf_name", "page_number", "chunk_text")
              .orderBy("pdf_name", "page_number"))
    except Exception as e:
        raise RuntimeError(
            f"Cannot read {EMBEDDINGS_TABLE}. "
            f"Ensure the table exists and you have SELECT privilege. Error: {e}"
        ) from e

    rows = df.collect()
    if not rows:
        raise RuntimeError(f"No rows in {EMBEDDINGS_TABLE} – run the pipeline first.")

    documents: List[Document] = []
    doc_ids   = set()
    total_tok = 0

    for row in rows:
        doc_id    = row["pdf_name"]
        page_number = row["page_number"] or 0
        text      = row["chunk_text"] or ""
        tok       = len(text.split())

        meta = clean_metadata({
            "document_id": doc_id,
            "page_number": page_number,
        })

        doc_ids.add(doc_id)
        total_tok += tok
        documents.append(Document(page_content=text, metadata=meta))

    stats = {
        "total_documents":      len(documents),
        "unique_sources":       len(doc_ids),
        "total_tokens":         total_tok,
        "avg_tokens_per_chunk": int(total_tok / len(documents)) if documents else 0,
    }

    logger.info(
        f"Loaded {len(documents):,} chunks from {len(doc_ids)} documents "
        f"({total_tok:,} tokens)"
    )
    return documents, stats


def inspect_documents(documents: List[Document], sample_size: int = 3):
    """Print a few sample documents for a quick sanity-check."""
    logger.info(f"\nSample documents ({min(sample_size, len(documents))}):")
    for i, doc in enumerate(documents[:sample_size]):
        chars = len(doc.page_content)
        logger.info(
            f"  [{i+1}] doc={doc.metadata.get('document_id')}  "
            f"page={doc.metadata.get('page_number')}  "
            f"chars={chars}"
        )
        preview = doc.page_content[:150].replace("\n", " ")
        logger.info(f"       {preview}…")

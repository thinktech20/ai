"""Experiment tracking enums for FSR v2 pipeline.

These enums enable repeatable experiments and method comparison across P1/P2:
- Type safety for method choices
- Single source of truth for valid values
- IDE navigation to implementation code
- MLflow integration for experiment tracking

Usage in P1 (enrichment.py):
    metadata_row["extractor_method"] = ExtractorMethod.PYPDF2_V1_0.value

Usage in P2 (chunking.py):
    chunk_metadata["chunking_strategy"] = ChunkingStrategy.MARKDOWN.value

Usage in MLflow:
    mlflow.log_params({
        "chunking_strategy": ChunkingStrategy.RECURSIVE.value,
        "embedding_model": EmbeddingModel.TEXT_EMBEDDING_3_LARGE.value,
    })
"""

from enum import Enum


class ExtractorMethod(Enum):
    """Text extraction tools for P1 metadata extraction."""

    PYPDF2_V1_0 = "pypdf2_v1.0"           # silver/src/etl/fsr_v2/parsing.py — matches DS-Guru extraction path
    PYMUPDF_V1_0 = "pymupdf_v1.0"         # silver/src/etl/fsr_v2/parsing.py — glyph-position-preserving extraction


class PreprocessMethod(Enum):
    """Preprocessor versions for P1 metadata extraction."""

    PREPROCESSOR_V2_FINAL = "preprocessor_v2_final"  # reference/preprocessor_v2_final.py


class LLMModelExtraction(Enum):
    """LLM models for P1 doc-level field extraction."""

    GPT_4_TURBO = "gpt-4-turbo"  # OpenAI, ~128k ctx
    CLAUDE_3_SONNET = "claude-3-sonnet"  # Anthropic, 200k ctx
    CLAUDE_3_OPUS = "claude-3-opus"  # Anthropic, higher accuracy


class LLMExtractionPromptVersion(Enum):
    """Prompt template versions for P1 LLM extraction."""

    V2_WITH_HINTS = "v2_with_hints"  # common/fsr_v2/prompts/normalization_prompt.py
    V3_SCHEMA_DRIVEN = "v3_schema_driven"  # future


class ChunkingStrategy(Enum):
    """Chunking methods in P2 merge + chunking step."""

    RECURSIVE = "recursive"  # common/fsr_v2/chunker.py → SmartChunker
    CHARACTER = "character"  # common/fsr_v2/chunker.py → SmartChunker
    MARKDOWN = "markdown"   # common/fsr_v2/chunker.py → SmartChunker
    SECTION = "section"     # common/fsr_v2/chunker.py → SmartChunker


class EmbeddingModel(Enum):
    """Embedding models for P2 embedding step."""

    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"  # OpenAI, dim=3072
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"  # OpenAI, dim=1536
    VOYAGE_3 = "voyage-3"  # Voyage AI, dim=1024


class MergeStrategy(Enum):
    """Merge logic versions in P2 merge step."""

    V2_4LEVEL_CASCADE = "v2_4level_cascade"  # gold/src/etl/fsr_v2/chunking.py → 4-level priority
    V2_DOC_SECTION_ONLY = "v2_doc_section_only"  # upload + doc + optional section, no region override


class RegionAttributionMethod(Enum):
    """Region matching methods for per-chunk ESN attribution in P2."""

    CHAR_OFFSET_MAX_OVERLAP = "char_offset_max_overlap"  # common/fsr_v2/region_utils.py → attribute_esn()
    CHAR_OFFSET_START_CHAR = "char_offset_start_char"  # common/fsr_v2/region_utils.py → attribute_esn(start_char)


# Chunk metadata JSON contract version.
# Bump this string when the schema of fsr_chunks_v2.metadata changes in a
# backward-incompatible way so consumers can detect and handle old rows.
CHUNK_METADATA_JSON_CONTRACT_VERSION = "fsr_v2_chunk_metadata_v2"

# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# mnd_chunking — M&D preprocessing, PII redaction, and chunking helpers.
#
# Sourced via `%run ../../../common/mnd_chunking`.  Depends on `mnd_config`
# being run first (for constants: MND_NULL_PROXIES, MND_BOILERPLATE_PHRASES,
# MND_URL_PATTERN, MND_SYSTEM_EMAILS, MND_PII_ENTITIES, MND_FLAIR_MODEL,
# MND_SSO_PATTERN, MND_TEXT_COLS, MND_CHUNK_TEXT_FIELDS, MND_CHUNK_TS_BOUNDARY,
# MND_CHUNK_MIN_TOKENS, MND_CHUNK_MAX_TOKENS, MND_CHUNK_TINY_TOKENS).
#
# What this module does:
#   - Standardise null-proxy strings ("", "N/A", "UNKNOWN", …) to true NULL
#   - Drop the 46 known empty / ETL-only source columns
#   - Cast text-typed numeric columns to DOUBLE/INT in `*_clean` columns
#   - Replace legacy -999.0 sentinels with NULL
#   - Filter out rows with missing / pre-1990 opened_at
#   - Derive `record_origin` (migrated_supportcentral vs native_servicenow)
#   - Select the 32-column handoff schema (drops sys_created_by)
#   - Strip 27 boilerplate phrases + URLs from the 7 text columns
#   - Pre-clean system emails / mailto / cid placeholders, normalise
#     obfuscated email forms, then run Presidio + Flair to redact
#     PERSON / EMAIL_ADDRESS / PHONE_NUMBER / SSO_ID
#   - 4-step chunking: timestamp-boundary split → merge < MIN tokens →
#     split > MAX tokens → backward merge < TINY tokens
#   - Finalise chunks with a deterministic md5 chunk_id, quality bucket,
#     and 30-column per-case metadata join
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

import hashlib
import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Iterable, List, Optional

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

_log = logging.getLogger("mnd.chunking")

# Composite key separator used to encode (serial_number, mnd_case_number)
# into a single Spark column during timestamp-boundary chunking.
_SEP = "|||"


# ─── Step 1: Null-proxy standardisation ────────────────────────────────────

def apply_null_proxies(df: DataFrame, proxies: Iterable[str]) -> DataFrame:
    """Replace every string column value matching `proxies` with true NULL.

    Equivalent to E3_final.py:apply_step1 — only StringType columns are
    affected.  Idempotent.
    """
    proxy_list = list(proxies)
    out = df
    for field in df.schema.fields:
        if "StringType" not in str(field.dataType):
            continue
        out = out.withColumn(
            field.name,
            F.when(F.col(field.name).isin(proxy_list), F.lit(None).cast("string"))
             .otherwise(F.col(field.name)),
        )
    return out


# ─── Step 2: Field exclusion ───────────────────────────────────────────────

def drop_excluded_fields(df: DataFrame, fields_to_exclude: Iterable[str]) -> DataFrame:
    """Drop the subset of `fields_to_exclude` that exist on `df`."""
    present = [f for f in fields_to_exclude if f in df.columns]
    return df.drop(*present) if present else df


# ─── Step 4: Numeric formatting ────────────────────────────────────────────

# Maps source column -> cleaned numeric column name.  These names match the
# research notebook's HANDOFF_FIELDS schema.
_NUMERIC_CLEAN_MAP = {
    "sys_mod_count": "sys_mod_count_clean",
    "u_speed_at_trip_event": "u_speed_at_trip_event_clean",
    "u_load_at_trip_event_mw_": "u_load_at_trip_event_mw_clean",
}


def add_numeric_clean_columns(df: DataFrame) -> DataFrame:
    """Cast numeric source columns to DOUBLE/INT, exposing `*_clean` columns.

    Source values are TEXT and may contain blanks, commas or non-numeric junk.
    `_clean` columns hold the cast value (NULL on parse failure) so downstream
    logic can rely on numeric typing without re-parsing each time.
    """
    out = df
    for src, clean in _NUMERIC_CLEAN_MAP.items():
        if src in out.columns and clean not in out.columns:
            cast_to = "int" if src == "sys_mod_count" else "double"
            out = out.withColumn(
                clean,
                F.col(src).cast("string").rlike(r"^-?\d+(\.\d+)?$").alias("_is_num")
                if False else  # keep linter quiet — actual cast below
                F.when(
                    F.col(src).cast("string").rlike(r"^-?\d+(\.\d+)?$"),
                    F.col(src).cast(cast_to),
                ).otherwise(F.lit(None).cast(cast_to)),
            )
    return out


# ─── Step 5: Sentinel -999.0 → NULL ────────────────────────────────────────

_SENTINEL_NUMERIC_COLS = (
    "u_speed_at_trip_event_clean",
    "u_load_at_trip_event_mw_clean",
)


def replace_sentinel_values(df: DataFrame, sentinel: float = -999.0) -> DataFrame:
    """Replace legacy DCS sentinel (-999.0) with NULL in numeric `_clean` cols."""
    out = df
    for col in _SENTINEL_NUMERIC_COLS:
        if col in out.columns:
            out = out.withColumn(
                col,
                F.when(F.col(col) == F.lit(sentinel), F.lit(None))
                 .otherwise(F.col(col)),
            )
    return out


# ─── Step 6: Date validity ─────────────────────────────────────────────────

def filter_invalid_dates(df: DataFrame, cutoff: str = "1990-01-01") -> DataFrame:
    """Drop rows where closed_at < opened_at (invalid date order).

    Mirrors E3_final.py Step 6 exactly — only removes records where
    closed_at IS NOT NULL AND opened_at IS NOT NULL AND closed_at < opened_at.
    No pre-1990 floor or NULL opened_at filter applied (not in E3 logic).
    """
    if "closed_at" not in df.columns or "opened_at" not in df.columns:
        return df
    return df.filter(
        ~(
            F.col("closed_at").isNotNull()
            & F.col("opened_at").isNotNull()
            & (F.col("closed_at") < F.col("opened_at"))
        )
    )


# ─── Step 12: Migrated vs Native segmentation ──────────────────────────────

def add_record_origin(df: DataFrame) -> DataFrame:
    """Derive `record_origin` from `sys_created_by`.

    sys_created_by == 'ge_conversion' → 'migrated_supportcentral'
    otherwise                         → 'native_servicenow'
    """
    if "sys_created_by" not in df.columns:
        return df.withColumn("record_origin", F.lit("native_servicenow"))
    return df.withColumn(
        "record_origin",
        F.when(F.col("sys_created_by") == F.lit("ge_conversion"),
               F.lit("migrated_supportcentral"))
         .otherwise(F.lit("native_servicenow")),
    )


def select_handoff_fields(df: DataFrame, handoff_fields: Iterable[str]) -> DataFrame:
    """Select handoff schema; drop `sys_created_by` if present (PII).

    Mirrors E3_final.py:Cell 11 — only fields that actually exist on the
    input are selected to allow incremental schema evolution upstream.
    """
    present = [f for f in handoff_fields if f in df.columns]
    out = df.select(*present)
    if "sys_created_by" in out.columns:
        out = out.drop("sys_created_by")
    return out


# ─── Step 10: Boilerplate phrase + URL removal ─────────────────────────────

def clean_boilerplate(
    df: DataFrame,
    text_cols: Iterable[str],
    phrases: Iterable[str],
    url_pattern: str,
) -> DataFrame:
    """Strip boilerplate phrases then URLs from each `text_cols` column.

    Pass 1: combined phrase regex via `|`.join(re.escape(p) for p in phrases).
    Pass 2: URL strip via `url_pattern`.
    Trailing whitespace trimmed after each pass.
    """
    phrase_pattern = "|".join(re.escape(p) for p in phrases)
    out = df

    for c in text_cols:
        if c not in out.columns:
            continue
        out = out.withColumn(
            c,
            F.trim(F.regexp_replace(F.col(c).cast("string"), phrase_pattern, " ")),
        )

    for c in text_cols:
        if c not in out.columns:
            continue
        out = out.withColumn(
            c, F.trim(F.regexp_replace(F.col(c), url_pattern, "")),
        )

    return out


# ─── PII: System email pre-clean + Presidio + Flair ────────────────────────
# Presidio + Flair are heavy imports (~1.5 GB Flair model on first load).
# We initialise lazily via globals so unit-import of this module is fast and
# so the model is shared across all per-record calls inside a worker.

_PRESIDIO_INITIALISED = False
_ANALYZER = None
_ANONYMIZER = None
_SYSTEM_EMAIL_RE = None


def _build_system_email_re(system_emails: Iterable[str]) -> "re.Pattern":
    pattern = "|".join(re.escape(e) for e in system_emails)
    return re.compile(pattern, re.IGNORECASE) if pattern else None


def init_presidio(
    system_emails: Iterable[str],
    pii_entities: Iterable[str],
    flair_model: str,
    sso_pattern: str,
) -> None:
    """Initialise Presidio + Flair lazily.  Idempotent — safe to call repeatedly.

    Builds the system-email regex, loads the Flair NER model, registers the
    custom SSO_ID pattern, and instantiates AnalyzerEngine + AnonymizerEngine.
    Models are kept on module-level globals so they survive across batches.
    """
    global _PRESIDIO_INITIALISED, _ANALYZER, _ANONYMIZER, _SYSTEM_EMAIL_RE
    if _PRESIDIO_INITIALISED:
        return

    _SYSTEM_EMAIL_RE = _build_system_email_re(system_emails)

    import os
    # Disable hf_transfer accelerator — the Databricks driver/worker
    # filesystem doesn't always have it, and the slower default path works.
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

    from presidio_analyzer import (
        AnalyzerEngine,
        RecognizerRegistry,
        EntityRecognizer,
        RecognizerResult,
        Pattern,
        PatternRecognizer,
    )
    from presidio_anonymizer import AnonymizerEngine
    from flair.data import Sentence
    from flair.models import SequenceTagger

    class _FlairRecognizer(EntityRecognizer):
        def __init__(self):
            self.tagger = SequenceTagger.load(flair_model)
            super().__init__(supported_entities=["PERSON"], name="FlairRecognizer")

        def load(self):
            pass

        def analyze(self, text, entities, nlp_artifacts=None):
            results = []
            sentence = Sentence(text)
            self.tagger.predict(sentence)
            for ent in sentence.get_spans("ner"):
                if ent.get_label("ner").value == "PER" and "PERSON" in entities:
                    results.append(
                        RecognizerResult(
                            entity_type="PERSON",
                            start=ent.start_position,
                            end=ent.end_position,
                            score=ent.score,
                        )
                    )
            return results

    sso_recognizer = PatternRecognizer(
        supported_entity="SSO_ID",
        patterns=[Pattern(name="sso_pattern", regex=sso_pattern, score=0.85)],
    )

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers()
    registry.add_recognizer(_FlairRecognizer())
    registry.add_recognizer(sso_recognizer)

    _ANALYZER = AnalyzerEngine(registry=registry, supported_languages=["en"])
    _ANONYMIZER = AnonymizerEngine()
    _PRESIDIO_INITIALISED = True
    _log.info(
        "Presidio + Flair initialised — model=%s, entities=%s",
        flair_model,
        list(pii_entities),
    )


def remove_system_emails(text: Optional[str]) -> Optional[str]:
    """Pre-Presidio cleaner — strip mailto wrappers, system emails, CIDs.

    Order matters:
      1. <mailto:…> and bare mailto:…
      2. known system emails (case-insensitive)
      3. obfuscated forms: john at ge dot com / jane(at)ge.com → normalise
      4. Outlook <cid:…> and bare cid:…
      5. collapse double spaces
    """
    if text is None:
        return None
    text = str(text)
    if not text.strip():
        return text

    text = re.sub(r"<mailto:[^>]+>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"mailto:[^\s>]+", "", text, flags=re.IGNORECASE)

    if _SYSTEM_EMAIL_RE is not None:
        text = _SYSTEM_EMAIL_RE.sub("", text)

    text = re.sub(
        r"([a-zA-Z0-9._%+\-]+)\s*\(at\)\s*([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
        r"\1@\2",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"([a-zA-Z0-9._%+\-]+)\s*\[at\]\s*([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
        r"\1@\2",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"([a-zA-Z0-9._%+\-]+)\s+at\s+([a-zA-Z0-9\-]+)\s+dot\s+([a-zA-Z]{2,})",
        r"\1@\2.\3",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"<cid:[^>]+>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcid:[^\s\]>]+", "", text, flags=re.IGNORECASE)

    text = re.sub(r" {2,}", " ", text).strip()
    return text


def presidio_anonymize(text: Optional[str], pii_entities: Iterable[str]) -> Optional[str]:
    """Run system-email pre-clean + Presidio + Flair on a single string.

    Returns the input unchanged when Presidio is not initialised, the input
    is empty, or analysis finds no entities.  Each hit is replaced with
    `[REDACTED_<ENTITY>]`.
    """
    if text is None:
        return None
    text = str(text)
    if text.strip() == "":
        return text

    text = remove_system_emails(text)

    if not _PRESIDIO_INITIALISED:
        return text

    from presidio_anonymizer.entities import OperatorConfig

    entities = list(pii_entities)
    try:
        results = _ANALYZER.analyze(text=text, entities=entities, language="en")
        if not results:
            return text
        operators = {
            e: OperatorConfig("replace", {"new_value": f"[REDACTED_{e}]"})
            for e in entities
        }
        return _ANONYMIZER.anonymize(
            text=text, analyzer_results=results, operators=operators
        ).text
    except Exception as exc:  # noqa: BLE001 — surface, don't crash the batch
        _log.warning("Presidio analyze/anonymize failed (returning input): %s", exc)
        return text


def apply_presidio_to_pdf(pandas_df, text_cols: Iterable[str], pii_entities: Iterable[str]):
    """Apply Presidio + Flair to each `text_cols` in a Pandas DataFrame.

    Operates row-wise inside the driver-side Pandas DF.  Caller is
    responsible for the Spark→Pandas (and back) bridge and for preserving
    row order via `__row_id`.
    """
    available = [c for c in text_cols if c in pandas_df.columns]
    for col in available:
        pandas_df[col] = pandas_df[col].apply(lambda v: presidio_anonymize(v, pii_entities))
    return pandas_df


# ─── Chunking pipeline (4 steps) ───────────────────────────────────────────

def build_merged_free_text(
    df: DataFrame,
    fields: Iterable[str] = None,
) -> DataFrame:
    """Concat the 4 chunk text fields into `merged_free_text`.

    Each non-empty field is prefixed with its label (e.g.
    `comments_and_work_notes: …`) so chunk headers preserve provenance.
    """
    fields = list(fields) if fields is not None else [
        "comments_and_work_notes", "description", "close_notes", "u_resolve_notes",
    ]
    parts = []
    for f in fields:
        if f in df.columns:
            parts.append(
                F.when(
                    F.col(f).isNotNull() & (F.trim(F.col(f)) != F.lit("")),
                    F.concat(F.lit(f + ": "), F.col(f)),
                )
            )
        else:
            parts.append(F.lit(None).cast("string"))
    return df.withColumn("merged_free_text", F.concat_ws(" | ", *parts))


def chunk_by_timestamp_case(
    df: DataFrame,
    text_col: str = "merged_free_text",
    boundary_pattern: str = None,
) -> DataFrame:
    """Split `text_col` at ServiceNow comment timestamp boundaries.

    Groups by composite key `serial_number|||number_`.  Uses posexplode +
    cumulative-sum window to bucket lines between boundaries.
    """
    boundary = boundary_pattern or r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - "

    base = (
        df
        .withColumn(
            "record_id",
            F.concat(F.col("u_serial_number"), F.lit(_SEP), F.col("number_")),
        )
        .select(
            F.col("record_id"),
            F.col(text_col).cast("string").alias("text"),
        )
        .filter(F.col("text").isNotNull())
        .withColumn("line_arr", F.split(F.col("text"), r"\r?\n"))
        .select("record_id", F.posexplode("line_arr").alias("line_num", "line"))
        .withColumn("line", F.trim(F.col("line")))
        .filter(F.length("line") > 0)
        .withColumn(
            "is_boundary",
            F.when(F.col("line").rlike(boundary), 1).otherwise(0),
        )
    )

    w = (
        Window.partitionBy("record_id")
              .orderBy("line_num")
              .rowsBetween(Window.unboundedPreceding, 0)
    )

    base = base.withColumn("chunk_id", F.sum("is_boundary").over(w))

    return (
        base
        .groupBy("record_id", "chunk_id")
        .agg(F.collect_list(F.struct("line_num", "line")).alias("lines"))
        .withColumn("lines_sorted", F.expr("transform(array_sort(lines), x -> x.line)"))
        .withColumn("chunk_text", F.concat_ws("\n", F.col("lines_sorted")))
        .filter(
            F.col("chunk_text").isNotNull()
            & (F.length(F.trim(F.col("chunk_text"))) > 0)
        )
        .withColumn("tokens", F.size(F.split(F.trim(F.col("chunk_text")), r"\s+")))
        .withColumn("source_field", F.lit(text_col))
        .select("record_id", "chunk_id", "chunk_text", "tokens", "source_field")
    )


def merge_chunks_by_datetime(df_in: DataFrame, min_tokens: int) -> DataFrame:
    """Merge chunks smaller than `min_tokens` in chronological order.

    Pulls chunks to the driver (already bounded by the upstream micro-batch
    size).  Two phases: sequential append into a buffer, then iterative
    merge for any sub-threshold remainder.
    """
    _ts_re = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

    def _extract_ts(text: str):
        m = _ts_re.search(text)
        if not m:
            return None
        try:
            return datetime.strptime(m.group(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    rows = (
        df_in
        .select("record_id", "source_field", "chunk_id", "chunk_text")
        .orderBy("record_id", "source_field", "chunk_id")
        .collect()
    )

    grouped = defaultdict(list)
    for r in rows:
        text = (r["chunk_text"] or "").strip()
        if not text:
            continue
        grouped[(r["record_id"], r["source_field"])].append(
            {"text": text, "tokens": len(text.split()), "ts": _extract_ts(text)}
        )

    output = []
    for (record_id, source_field), chunks in grouped.items():
        chunks.sort(key=lambda c: (c["ts"] is None, c["ts"] or datetime.min))

        phase1 = []
        buf_text, buf_tok = "", 0
        for c in chunks:
            if not buf_text:
                buf_text, buf_tok = c["text"], c["tokens"]
            elif buf_tok < min_tokens:
                buf_text += "\n" + c["text"]
                buf_tok = len(buf_text.split())
            else:
                phase1.append({"text": buf_text, "tokens": buf_tok})
                buf_text, buf_tok = c["text"], c["tokens"]
        if buf_text:
            phase1.append({"text": buf_text, "tokens": buf_tok})

        changed = True
        while changed and len(phase1) > 1:
            changed = False
            for i in range(len(phase1)):
                if phase1[i]["tokens"] >= min_tokens:
                    continue
                neighbor = i + 1 if i + 1 < len(phase1) else i - 1
                lo, hi = min(i, neighbor), max(i, neighbor)
                merged = phase1[lo]["text"] + "\n" + phase1[hi]["text"]
                phase1[lo] = {"text": merged, "tokens": len(merged.split())}
                phase1.pop(hi)
                changed = True
                break

        for c in phase1:
            output.append((record_id, source_field, c["text"], c["tokens"]))

    return spark.createDataFrame(
        output, ["record_id", "source_field", "chunk_text", "tokens"]
    )


def split_large_chunks_python(df_in: DataFrame, max_tokens: int) -> DataFrame:
    """Split chunks > max_tokens at paragraph then sentence boundaries."""
    rows = df_in.select("record_id", "source_field", "chunk_text").collect()
    output = []

    for r in rows:
        record_id = r["record_id"]
        source_field = r["source_field"]
        text = (r["chunk_text"] or "").strip()
        if not text:
            continue

        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        buffer, buffer_tokens = [], 0

        for p in paragraphs:
            p_tokens = len(p.split())

            if p_tokens > max_tokens:
                for s in [s.strip() for s in p.split(". ") if s.strip()]:
                    s_tokens = len(s.split())
                    if buffer and buffer_tokens + s_tokens > max_tokens:
                        out = "\n".join(buffer).strip()
                        if out:
                            output.append(
                                (record_id, source_field, out, len(out.split()))
                            )
                        buffer, buffer_tokens = [], 0
                    buffer.append(s)
                    buffer_tokens += s_tokens
                continue

            if buffer and buffer_tokens + p_tokens > max_tokens:
                out = "\n".join(buffer).strip()
                if out:
                    output.append((record_id, source_field, out, len(out.split())))
                buffer, buffer_tokens = [], 0
            buffer.append(p)
            buffer_tokens += p_tokens

        if buffer:
            out = "\n".join(buffer).strip()
            if out:
                output.append((record_id, source_field, out, len(out.split())))

    return spark.createDataFrame(
        output, ["record_id", "source_field", "chunk_text", "tokens"]
    )


def merge_tiny_chunks_backward(df_in: DataFrame, min_tokens: int) -> DataFrame:
    """Merge any chunk still < min_tokens into its preceding neighbour."""
    rows = df_in.select("record_id", "source_field", "chunk_text").collect()

    grouped = defaultdict(list)
    for r in rows:
        text = (r["chunk_text"] or "").strip()
        if text:
            grouped[(r["record_id"], r["source_field"])].append(
                {"text": text, "tokens": len(text.split())}
            )

    output = []
    for (record_id, source_field), chunks in grouped.items():
        changed = True
        while changed and len(chunks) > 1:
            changed = False
            for i in range(len(chunks)):
                if chunks[i]["tokens"] >= min_tokens:
                    continue
                target = i - 1 if i > 0 else i + 1
                lo, hi = min(i, target), max(i, target)
                merged = chunks[lo]["text"] + "\n" + chunks[hi]["text"]
                chunks[lo] = {"text": merged, "tokens": len(merged.split())}
                chunks.pop(hi)
                changed = True
                break
        for c in chunks:
            output.append((record_id, source_field, c["text"], c["tokens"]))

    return spark.createDataFrame(
        output, ["record_id", "source_field", "chunk_text", "tokens"]
    )


# ─── Chunk finalisation (decode key, deterministic id, join metadata) ──────

# Metadata columns to carry into each chunk row.  `_clean` columns are
# renamed back to SOT names during finalise.
_META_FIELDS = [
    "u_ccap_alarm_name",
    "u_component",
    "u_resolution_category",
    "u_major_equipment_association",
    "opened_at",
]


def _col_or_null(df: DataFrame, name: str):
    if name in df.columns:
        return F.col(name)
    return F.lit(None).cast("string").alias(name)


def build_chunk_metadata(df_src: DataFrame) -> DataFrame:
    """Project the source DataFrame down to per-case metadata for joining.

    Missing columns are emitted as NULL strings so the chunk-table schema is
    stable across upstream schema drift.
    """
    select_exprs = [F.col("number_").alias("mnd_case_number_meta")]
    for f in _META_FIELDS:
        if f in df_src.columns:
            select_exprs.append(F.col(f))
        else:
            select_exprs.append(F.lit(None).cast("string").alias(f))
    return df_src.select(*select_exprs).dropDuplicates(["mnd_case_number_meta"])


def finalise_chunks(
    df_chunks: DataFrame,
    df_src: DataFrame,
    strategy: str = "timestamp_boundary_case_level",
) -> DataFrame:
    """Add chunk_id (deterministic), chunk_index, quality, strategy, metadata.

    `chunk_id` is `md5(mnd_case_number + "_" + source_field + "_" + chunk_index)`
    (case, field, position) — no hash collision on identical chunk text.
    """
    df_meta = build_chunk_metadata(df_src)

    # chunk_id is positional: md5(mnd_case_number + "_" + source_field + "_" + chunk_index).
    # chunk_index is computed first (row_number ordered by chunk_text for
    # stability), then used as the hash input — always unique per (case, field).

    # chunk_index is display-only, ordered by chunk_text for stability.
    w_seq = (
        Window
        .partitionBy("record_id", "source_field")
        .orderBy("chunk_text")
    )

    return (
        df_chunks
        .withColumn(
            "serial_number",
            F.split(F.col("record_id"), r"\|\|\|").getItem(0),
        )
        .withColumn(
            "mnd_case_number",
            F.split(F.col("record_id"), r"\|\|\|").getItem(1),
        )
        .withColumn("chunk_index", F.row_number().over(w_seq))
        .withColumn(
            "chunk_id",
            F.md5(F.concat(
                F.col("mnd_case_number"),
                F.lit("_"),
                F.col("source_field"),
                F.lit("_"),
                F.col("chunk_index").cast("string"),
            )),
        )
        .withColumn("char_count", F.length("chunk_text"))
        .withColumn(
            "quality",
            F.when(F.col("tokens") < 256, F.lit("too_small"))
             .when(F.col("tokens") > 768, F.lit("too_large"))
             .otherwise(F.lit("in_target")),
        )
        .withColumn("strategy", F.lit(strategy))
        .withColumnRenamed("source_field", "field_name")
        .join(
            df_meta,
            F.col("mnd_case_number") == F.col("mnd_case_number_meta"),
            how="left",
        )
        .drop("mnd_case_number_meta")
        .withColumnRenamed("sys_mod_count_clean", "sys_mod_count")
        .withColumnRenamed("u_load_at_trip_event_mw_clean", "u_load_at_trip_event_mw_")
        .withColumnRenamed("u_speed_at_trip_event_clean", "u_speed_at_trip_event")
        .withColumnRenamed("opened_at", "created_at")
    )


# ─── Chunk-text metadata prefix ───────────────────────
# Case-level metadata fields prepended as a header line to chunk_text so the
# embedded text carries provenance/context.
# Applied AFTER finalise_chunks so chunk_id stays keyed on the body text
# (idempotent MERGE), while the stored/embedded chunk_text is prefixed.
_PREFIX_FIELDS = [
    "number_",
    "priority",
    "u_ccap_alarm_name",
    "u_component",
    "u_resolution_category",
    "u_section",
    "u_serial_number",
    "u_site_station_name",
    "u_status",
    "u_type",
    "u_equipment_name",
    "u_major_equipment_association",
]


def build_chunk_prefix(df_src: DataFrame) -> DataFrame:
    """Build a per-case `_prefix_text` header from `_PREFIX_FIELDS`.

    Each present, non-blank field becomes `field: value`; parts are joined
    with " | ".  Keyed on `number_` (= mnd_case_number).  Missing columns are
    skipped so the header is stable across upstream schema drift.
    """
    available = [f for f in _PREFIX_FIELDS if f in df_src.columns]
    parts = [
        F.when(
            F.col(f).isNotNull() & (F.trim(F.col(f).cast("string")) != F.lit("")),
            F.concat(F.lit(f + ": "), F.col(f).cast("string")),
        )
        for f in available
    ]
    return (
        df_src
        .select(
            F.col("number_").alias("_prefix_case_number"),
            F.concat_ws(" | ", *parts).alias("_prefix_text"),
        )
        .dropDuplicates(["_prefix_case_number"])
    )


def apply_chunk_prefix(df_chunks: DataFrame, df_src: DataFrame) -> DataFrame:
    """Prepend the per-case metadata header to `chunk_text`.

    Produces `<prefix>\\n<chunk_text>` when the prefix is non-empty, else
    leaves chunk_text unchanged.  Must run AFTER `finalise_chunks` so
    `chunk_id` is keyed on the body text (not the prefixed text) — this keeps
    the MERGE into the chunk table idempotent across re-runs.
    """
    df_prefix = build_chunk_prefix(df_src)
    return (
        df_chunks
        .join(
            df_prefix,
            F.col("mnd_case_number") == F.col("_prefix_case_number"),
            how="left",
        )
        .withColumn(
            "chunk_text",
            F.when(
                F.col("_prefix_text").isNotNull()
                & (F.length(F.trim(F.col("_prefix_text"))) > 0),
                F.concat(F.col("_prefix_text"), F.lit("\n"), F.col("chunk_text")),
            ).otherwise(F.col("chunk_text")),
        )
        .drop("_prefix_case_number", "_prefix_text")
    )

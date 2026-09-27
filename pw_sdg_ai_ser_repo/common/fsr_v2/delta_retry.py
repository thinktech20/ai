"""Delta write-conflict retry, shared by the P1 (silver) and P2 (gold) pipelines.

Lives in common/ because `silver/src/etl/fsr_v2` and `gold/src/etl/fsr_v2` are
two different packages that happen to share a name and must never both sit on
sys.path in one session — so neither can import the other.
"""
from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

log = logging.getLogger("fsr.v2.delta")

# Matched against the exception text rather than the type: Delta surfaces these
# as several different classes and error codes depending on runtime and
# statement kind.
#
# The conflict source is usually not another pipeline run — it is most often
# Delta autoOptimize/optimizeWrite committing in the background, which is
# enabled on fsr_metadata_v2. Retrying is the supported handling for
# optimistic-concurrency conflicts; without it a document lands in
# metadata_status='failed' purely from commit timing.
CONCURRENCY_ERROR_MARKERS = (
    "DELTA_CONCURRENT_APPEND",
    "ConcurrentAppendException",
    "DELTA_CONCURRENT_DELETE_READ",
    "ConcurrentDeleteReadException",
    "DELTA_CONCURRENT_DELETE_DELETE",
    "ConcurrentDeleteDeleteException",
    "DELTA_CONCURRENT_TRANSACTION",
    "ConcurrentTransactionException",
    "DELTA_CONCURRENT_WRITE",
    "ConcurrentWriteException",
    "METADATA_CHANGED",
    "MetadataChangedException",
    "PROTOCOL_CHANGED",
    "ProtocolChangedException",
)

MERGE_MAX_ATTEMPTS = 5
MERGE_BASE_BACKOFF_S = 1.5


def is_concurrency_error(exc: Exception) -> bool:
    text = str(exc)
    return any(marker in text for marker in CONCURRENCY_ERROR_MARKERS)


def run_with_retry(spark: "SparkSession", sql: str, label: str) -> None:
    """Execute a write statement, retrying with jittered backoff on Delta conflicts.

    Only concurrency errors are retried; anything else re-raises immediately so a
    genuine bug is not hidden behind five silent attempts.
    """
    for attempt in range(1, MERGE_MAX_ATTEMPTS + 1):
        try:
            spark.sql(sql)
            if attempt > 1:
                log.info("  [RETRY-OK] %s: succeeded on attempt %d", label[:60], attempt)
            return
        except Exception as e:
            if not is_concurrency_error(e) or attempt == MERGE_MAX_ATTEMPTS:
                raise
            # Jitter matters: fixed backoff makes the same writers collide again.
            delay = MERGE_BASE_BACKOFF_S * (2 ** (attempt - 1)) * (0.5 + random.random())
            log.warning(
                "  [WRITE-CONFLICT] %s: attempt %d/%d hit a write conflict, retrying in %.1fs",
                label[:60], attempt, MERGE_MAX_ATTEMPTS, delay,
            )
            time.sleep(delay)

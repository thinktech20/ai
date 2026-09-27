"""Unit tests for the shared Delta write-conflict retry."""
import time
import unittest
from unittest.mock import MagicMock

from common.fsr_v2.delta_retry import (
    CONCURRENCY_ERROR_MARKERS,
    MERGE_MAX_ATTEMPTS,
    is_concurrency_error,
    run_with_retry,
)


class TestIsConcurrencyError(unittest.TestCase):
    def test_recognises_every_declared_marker(self):
        for marker in CONCURRENCY_ERROR_MARKERS:
            self.assertTrue(
                is_concurrency_error(Exception(f"[{marker}] table was modified")),
                f"{marker} should be treated as a concurrency error",
            )

    def test_p1_markers_still_covered_after_move_to_common(self):
        # These were in silver's private list before it was shared with P2.
        # Losing any of them would silently weaken P1's retry.
        for marker in (
            "DELTA_CONCURRENT_APPEND", "ConcurrentAppendException",
            "DELTA_CONCURRENT_DELETE_READ", "ConcurrentDeleteReadException",
            "DELTA_CONCURRENT_DELETE_DELETE", "ConcurrentDeleteDeleteException",
            "DELTA_CONCURRENT_TRANSACTION", "ConcurrentTransactionException",
            "METADATA_CHANGED", "MetadataChangedException",
        ):
            self.assertIn(marker, CONCURRENCY_ERROR_MARKERS)

    def test_unrelated_errors_are_not_concurrency(self):
        for msg in ("AnalysisException: cannot resolve column",
                    "Cannot open empty file",
                    "TABLE_OR_VIEW_NOT_FOUND"):
            self.assertFalse(is_concurrency_error(Exception(msg)), msg)


class TestRunWithRetry(unittest.TestCase):
    def test_succeeds_first_try_runs_once(self):
        spark = MagicMock()
        run_with_retry(spark, "MERGE 1", "label")
        spark.sql.assert_called_once_with("MERGE 1")

    def test_retries_concurrency_error_then_succeeds(self):
        spark = MagicMock()
        spark.sql.side_effect = [Exception("ConcurrentAppendException"), None]
        run_with_retry(spark, "MERGE 2", "label")
        self.assertEqual(spark.sql.call_count, 2)

    def test_non_concurrency_error_raises_immediately(self):
        spark = MagicMock()
        spark.sql.side_effect = Exception("AnalysisException: bad column")
        with self.assertRaises(Exception):
            run_with_retry(spark, "MERGE 3", "label")
        # Must not burn retries on a real bug.
        self.assertEqual(spark.sql.call_count, 1)

    def test_gives_up_after_max_attempts_and_reraises(self):
        spark = MagicMock()
        spark.sql.side_effect = Exception("DELTA_CONCURRENT_APPEND")
        with self.assertRaises(Exception):
            run_with_retry(spark, "MERGE 4", "label")
        self.assertEqual(spark.sql.call_count, MERGE_MAX_ATTEMPTS)

    def test_backoff_is_jittered_not_fixed(self):
        # Fixed backoff makes the same writers collide again on the next attempt.
        delays = []
        real_sleep = time.sleep
        try:
            time.sleep = lambda d: delays.append(d)  # noqa: E731
            for _ in range(6):
                spark = MagicMock()
                spark.sql.side_effect = [Exception("ConcurrentAppendException"), None]
                run_with_retry(spark, "MERGE", "label")
        finally:
            time.sleep = real_sleep
        self.assertGreater(len(set(delays)), 1, "first-attempt delay should vary between runs")

    def test_backoff_grows_between_attempts(self):
        delays = []
        real_sleep = time.sleep
        try:
            time.sleep = lambda d: delays.append(d)  # noqa: E731
            spark = MagicMock()
            spark.sql.side_effect = Exception("ConcurrentAppendException")
            with self.assertRaises(Exception):
                run_with_retry(spark, "MERGE", "label")
        finally:
            time.sleep = real_sleep
        self.assertEqual(len(delays), MERGE_MAX_ATTEMPTS - 1)
        # Jitter is 0.5-1.5x, so consecutive delays can overlap; compare ends instead.
        self.assertGreater(delays[-1], delays[0])


if __name__ == "__main__":
    unittest.main()

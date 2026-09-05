"""Shared global lock for PyMuPDF access in multi-threaded Databricks runs."""

from contextlib import contextmanager
import os
import threading


_PYMUPDF_LOCK = threading.Lock()


@contextmanager
def hold_pymupdf_lock():
    """Serialize all PyMuPDF native calls across worker threads."""
    use_lock = os.getenv("FSR_USE_PYMUPDF_LOCK", "true").strip().lower() not in {
        "0", "false", "f", "no", "n", "off"
    }
    if not use_lock:
        yield
        return
    with _PYMUPDF_LOCK:
        yield
"""
Sandboxed per-collection metadata preprocessor.

A user authors a ``preprocess(ctx)`` function that runs once per document,
BEFORE the LLM metadata extraction, to deterministically improve metadata
correctness. It can:
  - set/override schema field values (document level),
  - provide correcting "hints" to the LLM extraction prompt,
  - tag character-offset regions so each chunk inherits the right values
    (per-section metadata).

Security model (in-process, trusted single-tenant tool):
  - The source is validated with an AST allowlist BEFORE execution: no imports,
    no ``eval``/``exec``/``open``/``compile``/``__import__``/``getattr`` etc.,
    and no dunder attribute access (blocks ``().__class__.__bases__`` escapes).
  - Execution uses a restricted ``__builtins__`` namespace plus a small set of
    pre-injected safe modules (``re``, ``json``, ``datetime``).
  - The function runs in an **isolated child process** with a scrubbed
    environment and hard resource caps (``RLIMIT_CPU`` + ``RLIMIT_AS``); the
    parent force-kills it if it overruns the wall-clock budget. This bounds CPU,
    memory, and information exposure even if the allowlist is bypassed.
"""

from __future__ import annotations

import ast
import json as _json
import logging
import math
import multiprocessing
import os
import queue as _queue
import re as _re
import datetime as _datetime
import signal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Result caps (defensive)
MAX_HINTS_CHARS = 6000
MAX_METADATA_KEYS = 100
MAX_METADATA_VALUE_CHARS = 2000
MAX_REGIONS = 5000
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_MEMORY_BYTES = 512 * 1024 * 1024  # address-space cap for the child process
_WALL_GRACE_SECONDS = 2.0             # wall-clock slack over the CPU limit

# Names that must never be referenced (escape vectors / I/O)
_FORBIDDEN_NAMES = {
    "eval", "exec", "compile", "open", "__import__", "input", "breakpoint",
    "getattr", "setattr", "delattr", "globals", "locals", "vars",
    "type", "object", "super", "help", "memoryview", "classmethod",
    "staticmethod", "property", "__builtins__",
}

# Curated safe builtins exposed to preprocessor code
_SAFE_BUILTINS = {
    name: __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name)
    for name in (
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
        "int", "isinstance", "len", "list", "map", "max", "min", "range",
        "round", "set", "frozenset", "sorted", "str", "sum", "tuple", "zip",
        "reversed", "repr", "chr", "ord",
    )
}


class PreprocessorError(Exception):
    """Raised for validation, execution, or timeout failures."""


class PreprocessorContext:
    """Read-only inputs passed to the user's ``preprocess(ctx)`` function."""

    def __init__(self, filename: str, full_text: str, pages: List[str],
                 page_offsets: List[Dict[str, int]], fields: List[Dict[str, Any]]):
        self.filename = filename
        self.full_text = full_text
        self.pages = pages
        self.page_offsets = page_offsets
        self.fields = fields


def validate_code(code: str) -> None:
    """Static AST allowlist check. Raises PreprocessorError on any violation."""
    if not code or not code.strip():
        raise PreprocessorError("Preprocessor code is empty")
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        raise PreprocessorError(f"Syntax error: {e}")

    has_preprocess = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise PreprocessorError("import statements are not allowed")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                raise PreprocessorError(f"access to dunder attribute '{node.attr}' is not allowed")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise PreprocessorError(f"use of '{node.id}' is not allowed")
        if isinstance(node, ast.FunctionDef) and node.name == "preprocess":
            has_preprocess = True

    if not has_preprocess:
        raise PreprocessorError("code must define a function named 'preprocess(ctx)'")


def _build_namespace() -> Dict[str, Any]:
    """Restricted global namespace for executing preprocessor code."""
    return {
        "__builtins__": dict(_SAFE_BUILTINS),
        "re": _re,
        "json": _json,
        "datetime": _datetime,
    }


def _execute(code: str, ctx: PreprocessorContext) -> Dict[str, Any]:
    """Validate, load, run, and normalize a preprocessor in the current process."""
    validate_code(code)
    ns = _build_namespace()
    try:
        compiled = compile(code, "<preprocessor>", "exec")
        exec(compiled, ns)  # noqa: S102 — restricted namespace
    except Exception as e:  # noqa: BLE001
        raise PreprocessorError(f"Failed to load preprocessor: {e}")
    fn = ns.get("preprocess")
    if not callable(fn):
        raise PreprocessorError("code must define a callable 'preprocess(ctx)'")
    return _validate_result(fn(ctx))


def _apply_rlimits(cpu_seconds: int, mem_bytes: int) -> None:
    """Best-effort hard CPU + address-space caps for the child process."""
    try:
        import resource
    except ImportError:  # non-POSIX (e.g. Windows) — no rlimit support
        return
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
    except (ValueError, OSError):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    except (ValueError, OSError):
        pass  # RLIMIT_AS is not enforced on some platforms (e.g. macOS)


def _subprocess_entry(code, ctx, cpu_seconds, mem_bytes, q) -> None:
    """Child entrypoint: scrub env, cap resources, run, return result via queue."""
    try:
        os.environ.clear()  # drop inherited secrets before any user code runs
    except Exception:  # noqa: BLE001
        pass
    _apply_rlimits(cpu_seconds, mem_bytes)
    try:
        q.put(("ok", _execute(code, ctx)))
    except PreprocessorError as e:
        q.put(("err", str(e)))
    except MemoryError:
        q.put(("err", "Preprocessor exceeded its memory limit"))
    except Exception as e:  # noqa: BLE001
        q.put(("err", f"{type(e).__name__}: {e}"))


def _mp_context():
    """Pick a start method for the child process.

    ``forkserver`` and ``spawn`` fork from a clean, single-threaded helper so the
    child cannot inherit a locked mutex from the multithreaded API server (a
    plain ``fork`` deadlocks in that case). ``fork`` is only the last resort for
    platforms that offer nothing else.
    """
    available = set(multiprocessing.get_all_start_methods())
    for method in ("forkserver", "spawn", "fork"):
        if method in available:
            return multiprocessing.get_context(method)
    return multiprocessing.get_context()


def _terminate(proc) -> None:
    """SIGTERM then SIGKILL a child that is still alive; reap it."""
    if proc.is_alive():
        proc.terminate()
        proc.join(1.0)
    if proc.is_alive():
        proc.kill()
        proc.join(1.0)


def _coerce_metadata(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    for i, (k, v) in enumerate(raw.items()):
        if i >= MAX_METADATA_KEYS:
            break
        if v is None:
            continue
        if isinstance(v, (list, tuple, set)):
            v = ", ".join(str(x) for x in v)
        elif isinstance(v, dict):
            continue
        v = str(v)
        if len(v) > MAX_METADATA_VALUE_CHARS:
            v = v[:MAX_METADATA_VALUE_CHARS]
        out[str(k)] = v
    return out


def _coerce_regions(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw[:MAX_REGIONS]:
        if not isinstance(item, dict):
            continue
        try:
            start = int(item.get("start"))
            end = int(item.get("end"))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        meta = _coerce_metadata(item.get("metadata"))
        if not meta:
            continue
        out.append({"start": start, "end": end, "metadata": meta})
    return out


def _validate_result(result: Any) -> Dict[str, Any]:
    if result is None:
        return {"metadata": {}, "hints": "", "regions": []}
    if not isinstance(result, dict):
        raise PreprocessorError("preprocess() must return a dict (or None)")
    hints = result.get("hints") or ""
    if not isinstance(hints, str):
        hints = str(hints)
    if len(hints) > MAX_HINTS_CHARS:
        hints = hints[:MAX_HINTS_CHARS]
    return {
        "metadata": _coerce_metadata(result.get("metadata")),
        "hints": hints,
        "regions": _coerce_regions(result.get("regions")),
    }


def run_preprocessor(code: str, ctx: PreprocessorContext,
                     timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """Validate and execute a preprocessor in an isolated, resource-capped process.

    The child runs with a hard CPU-time limit (``RLIMIT_CPU``), an address-space
    cap (``RLIMIT_AS``), and a scrubbed environment, and is force-killed if it
    overruns the wall-clock budget. Returns
    ``{"metadata": {...}, "hints": "...", "regions": [...]}``.
    Raises ``PreprocessorError`` on validation/execution/timeout/limit failure.
    """
    validate_code(code)  # fast fail in-parent; don't spawn for invalid code

    cpu_seconds = max(1, int(math.ceil(timeout)))
    wall_timeout = timeout + _WALL_GRACE_SECONDS

    try:
        mp_ctx = _mp_context()
        q = mp_ctx.Queue()
        proc = mp_ctx.Process(
            target=_subprocess_entry,
            args=(code, ctx, cpu_seconds, MAX_MEMORY_BYTES, q),
            daemon=True,
        )
        proc.start()
    except (OSError, ValueError) as e:
        raise PreprocessorError(f"Could not start isolated preprocessor: {e}")

    kind = payload = None
    try:
        try:
            kind, payload = q.get(timeout=wall_timeout)
        except _queue.Empty:
            pass
    finally:
        _terminate(proc)

    if kind == "ok":
        return payload
    if kind == "err":
        raise PreprocessorError(payload)

    # No result delivered → killed by a resource limit or the wall-clock guard.
    exitcode = proc.exitcode
    if exitcode is not None and exitcode < 0 and -exitcode == getattr(signal, "SIGXCPU", None):
        raise PreprocessorError(f"Preprocessor exceeded the {cpu_seconds}s CPU limit")
    raise PreprocessorError(f"Preprocessor timed out after {timeout:g}s")


def build_page_context(full_text: str, page_info: Optional[List[Dict[str, Any]]]):
    """Derive (pages, page_offsets) for the context from full_text + page_info.

    ``page_info`` is the list of {page,start,end} char ranges produced during
    PDF extraction. For non-paged content a single page spanning the whole text
    is returned.
    """
    if page_info:
        offsets = [
            {"page": p.get("page"), "start": int(p.get("start", 0)), "end": int(p.get("end", 0))}
            for p in page_info
        ]
        pages = [full_text[o["start"]:o["end"]] for o in offsets]
        return pages, offsets
    return [full_text], [{"page": 1, "start": 0, "end": len(full_text)}]

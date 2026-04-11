"""Lightweight regression checks for executor OpenClaw helpers.

Run from repo root:
  python executor/test_openclaw_classification.py

Or from executor/:
  python test_openclaw_classification.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_executor():
    here = Path(__file__).resolve().parent
    mod_path = here / "executor.py"
    name = "jarvis_executor_impl"
    spec = importlib.util.spec_from_file_location(name, mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    m = _load_executor()

    assert m._sanitize_error_excerpt("Bearer abcdefghi") == "Bearer [REDACTED]"
    assert "[REDACTED]" in m._sanitize_error_excerpt('api_key=secret123')

    assert m._classify_empty_or_stderr(stderr="", returncode=None) == m.ERROR_CLASS_EMPTY_OUTPUT
    assert (
        m._classify_empty_or_stderr(stderr="HTTP 401 Unauthorized", returncode=1)
        == m.ERROR_CLASS_AUTH_OR_CONFIG
    )
    assert m._classify_empty_or_stderr(stderr="oops", returncode=7) == m.ERROR_CLASS_NONZERO_EXIT

    assert "timed out" in m._failure_summary_for_user(m.ERROR_CLASS_TIMEOUT).lower()
    assert m._failure_summary_for_user("not_a_real_class") == m.FALLBACK_ERROR

    print("executor/test_openclaw_classification.py: ok")


if __name__ == "__main__":
    main()

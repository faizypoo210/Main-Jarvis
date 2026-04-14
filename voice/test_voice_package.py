"""Smoke: voice package must import the same way uvicorn does (repo root on sys.path).

Run: python -m pytest voice/test_voice_package.py -v
"""

from __future__ import annotations


def test_voice_server_app_imports() -> None:
    """Catch ModuleNotFoundError for sibling modules when using ``python -m uvicorn voice.server:app``."""
    from voice.server import app

    assert app.title == "JARVIS Voice"

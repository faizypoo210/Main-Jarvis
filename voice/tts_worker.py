"""One-shot pyttsx3 / SAPI synthesis for a subprocess only.

Run as ``python -m voice.tts_worker`` with UTF-8 text on stdin; WAV bytes on stdout.
A fresh engine each call avoids Windows multi-turn SAPI instability. Do not import the voice server.
"""

from __future__ import annotations

import os
import sys
import tempfile


def main() -> int:
    try:
        raw = sys.stdin.buffer.read()
        text = raw.decode("utf-8")
    except Exception as e:  # pragma: no cover
        print(str(e), file=sys.stderr)
        return 2
    if not (text or "").strip():
        print("empty tts text", file=sys.stderr)
        return 2

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.save_to_file(text, path)
        engine.runAndWait()
        with open(path, "rb") as f:
            data = f.read()
        if not data:
            print("empty wav output", file=sys.stderr)
            return 3
        sys.stdout.buffer.write(data)
    except Exception as e:  # pragma: no cover
        print(repr(e), file=sys.stderr)
        return 1
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

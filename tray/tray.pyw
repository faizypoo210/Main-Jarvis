"""
JARVIS system tray — pystray + Pillow. No console (run with pythonw).
"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw
from pystray import MenuItem as item

JARVIS_ROOT = Path(__file__).resolve().parent.parent


def _build_icon_image() -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    m = 3
    draw.ellipse((m, m, size - m, size - m), fill=(18, 22, 30, 255))
    cx = cy = size // 2
    layers = ((20, 35), (14, 70), (9, 130), (5, 200), (3, 255))
    for radius, alpha in layers:
        r, g, b = 88, 166, 255
        draw.ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            fill=(r, g, b, alpha),
        )
    return img


def _open(url: str) -> None:
    webbrowser.open(url)


def _stop_jarvis_stack() -> None:
    mypid = os.getpid()
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    with open(os.devnull, "wb") as devnull:
        subprocess.run(
            ["docker", "stop", "jarvis-postgres", "jarvis-redis"],
            stdout=devnull,
            stderr=devnull,
            creationflags=creationflags,
        )

    root_escaped = str(JARVIS_ROOT).replace("'", "''")
    ps = f"""
$me = {mypid}
$root = '{root_escaped}'
Get-CimInstance Win32_Process | Where-Object {{
  $_.CommandLine -and ($_.CommandLine -like ('*' + $root + '*')) -and $_.ProcessId -ne $me
}} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}
"""
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps,
        ],
        creationflags=creationflags,
    )


def _on_stop(icon: pystray.Icon, _item: pystray.MenuItem | None) -> None:
    _stop_jarvis_stack()
    icon.stop()


def _on_exit(icon: pystray.Icon, _item: pystray.MenuItem | None) -> None:
    icon.stop()


def _on_ready(ic: pystray.Icon) -> None:
    ic.visible = True
    ic.notify("JARVIS Online", title="JARVIS")


def main() -> None:
    image = _build_icon_image()
    icon = pystray.Icon(
        "jarvis",
        image,
        "JARVIS",
        menu=pystray.Menu(
            item("Open Jarvis", lambda i, it: _open("http://localhost:8000")),
            item("Open Dashboard", lambda i, it: _open("http://localhost:8080")),
            item("Open Mission Control", lambda i, it: _open("http://localhost:3000")),
            pystray.Menu.SEPARATOR,
            item("Stop JARVIS", _on_stop),
            item("Exit Tray", _on_exit),
        ),
    )
    icon.run(setup=_on_ready)


if __name__ == "__main__":
    main()

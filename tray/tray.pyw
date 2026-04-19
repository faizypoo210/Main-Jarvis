"""
JARVIS system tray — pystray + Pillow. No console (run with pythonw).
"""

from __future__ import annotations

import webbrowser

import pystray
from PIL import Image, ImageDraw
from pystray import MenuItem as item


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


def stop_jarvis(icon, item):
    import os
    import subprocess

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bat_path = os.path.join(repo_root, "jarvis-stop.bat")
    if not os.path.isfile(bat_path):
        icon.notify("jarvis-stop.bat not found", "JARVIS")
        icon.stop()
        return
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    icon.notify("Stopping JARVIS...", "JARVIS")
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
            item("Open Command Center", lambda i, it: _open("http://localhost:5173")),
            item("Open Control Plane (API)", lambda i, it: _open("http://localhost:8001/docs")),
            item("Open Voice Server", lambda i, it: _open("http://localhost:8000")),
            item("Open LobsterBoard", lambda i, it: _open("http://localhost:8080")),
            item("Open Mission Control (legacy)", lambda i, it: _open("http://localhost:3000")),
            pystray.Menu.SEPARATOR,
            item("Stop JARVIS", stop_jarvis),
            item("Exit Tray", _on_exit),
        ),
    )
    icon.run(setup=_on_ready)


if __name__ == "__main__":
    main()

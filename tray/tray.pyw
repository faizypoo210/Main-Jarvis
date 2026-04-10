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
    import subprocess

    # Kill by port - covers voice(8000), lobsterboard(8080),
    # mission control(3000,3001), openclaw(18789)
    for port in [8000, 8080, 3000, 3001, 18789]:
        subprocess.run(
            f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{port} ^| findstr LISTENING\') do taskkill /F /PID %a',
            shell=True, capture_output=True
        )

    # Stop Docker containers using full Docker Desktop path
    docker_paths = [
        r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
        "docker"
    ]
    for docker in docker_paths:
        result = subprocess.run(
            [docker, "ps", "-q"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            ids = result.stdout.strip().split()
            subprocess.run([docker, "stop"] + ids, capture_output=True)
            break

    # Kill python/node processes
    for proc in ["python.exe", "pythonw.exe", "node.exe"]:
        subprocess.run(["taskkill", "/F", "/IM", proc], capture_output=True)

    icon.notify("JARVIS Offline", "All services stopped.")
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
            item("Stop JARVIS", stop_jarvis),
            item("Exit Tray", _on_exit),
        ),
    )
    icon.run(setup=_on_ready)


if __name__ == "__main__":
    main()

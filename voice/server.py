"""
JARVIS Voice Server — FastAPI + WebSocket, faster-whisper STT, Ollama (default qwen3:4b), pyttsx3 TTS, Redis streams.

MACHINE_CONFIG_REQUIRED: REDIS_URL, CONTROL_PLANE_URL, Ollama/Whisper env; local .env beside this file.
UPSTREAM_DEPENDENCY: faster-whisper, pyttsx3, and optional GPU — not pinned to CI here.
TRUTH_SOURCE: intent forwarding targets control plane HTTP; mission truth remains control plane + DB.

Voice approval v1: approval_voice.try_handle_voice_approval; briefing_voice.try_handle_voice_briefing (read-only).
Both run before POST /commands. "Read that again" repeats the last briefing or approval reply (ephemeral).
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import sys
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from approval_voice import forget_voice_approval_state, try_handle_voice_approval
from briefing_voice import forget_voice_briefing_state, try_handle_voice_briefing

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jarvis.voice")

load_dotenv(Path(__file__).resolve().parent / ".env")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
# Override with CONTROL_PLANE_URL if the control plane listens elsewhere.
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8001").rstrip("/")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
if WHISPER_DEVICE == "cuda":
    WHISPER_COMPUTE = "float16"
else:
    WHISPER_COMPUTE = "int8"

STREAM_UPDATES = "jarvis.updates"

OLLAMA_ACK_SYSTEM = (
    "You are Jarvis, a calm executive AI assistant. "
    "Acknowledge the user's command in 1-2 sentences. "
    "Be brief. Confirm what you understood and that you are on it. "
    "Do not make up information. Do not invent results."
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

_model = None
_redis: Redis | None = None
_manager = None
_updates_task: asyncio.Task | None = None
_worker_hb_task: asyncio.Task | None = None

# Last spoken reply per WebSocket (briefing or approval) for "read that again"
_last_voice_reply: dict[int, str] = {}

RE_VOICE_READ_AGAIN = re.compile(
    r"\b(read\s+that\s+again|repeat\s+(that|it|the\s+approval)|say\s+that\s+again)\b",
    re.I,
)


def _norm_for_intent(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _forget_voice_session(ws_key: int) -> None:
    forget_voice_approval_state(ws_key)
    forget_voice_briefing_state(ws_key)
    _last_voice_reply.pop(ws_key, None)


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel("base", device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)
    return _model


def _tts_wav_bytes(text: str) -> bytes:
    import pyttsx3

    engine = pyttsx3.init()
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        engine.save_to_file(text, path)
        engine.runAndWait()
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _transcribe_file(path: str) -> str:
    model = _get_model()
    segments, _ = model.transcribe(path, language="en")
    return "".join(s.text for s in segments).strip()


async def post_command_to_control_plane(text: str) -> str | None:
    """POST command to the Jarvis control plane; return mission_id or None on failure."""
    url = f"{CONTROL_PLANE_URL}/api/v1/commands"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {"x-api-key": os.getenv("CONTROL_PLANE_API_KEY", "")}
            r = await client.post(
                url, json={"text": text, "source": "voice"}, headers=headers
            )
            r.raise_for_status()
            body = r.json()
            mid = body.get("mission_id")
            if mid is None:
                log.warning("control plane response missing mission_id: %s", body)
                return None
            return str(mid)
    except Exception as e:
        log.warning("control plane command post failed: %s", e)
        return None


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def send_json(self, ws: WebSocket, data: dict) -> None:
        await ws.send_json(data)

    async def broadcast_json(self, data: dict) -> None:
        async with self._lock:
            dead: list[WebSocket] = []
            for ws in self._clients:
                try:
                    await ws.send_json(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)

    async def count_clients(self) -> int:
        async with self._lock:
            return len(self._clients)


async def _tts_and_broadcast(manager: ConnectionManager, text: str, *, kind: str) -> None:
    if not text.strip():
        return
    loop = asyncio.get_event_loop()
    wav = await loop.run_in_executor(None, _tts_wav_bytes, text)
    b64 = base64.b64encode(wav).decode("ascii")
    await manager.broadcast_json({"type": "tts", "kind": kind, "text": text, "audio_b64": b64})


async def _redis_updates_loop(manager: ConnectionManager) -> None:
    assert _redis is not None
    last_id = "$"
    while True:
        try:
            out = await _redis.xread({STREAM_UPDATES: last_id}, block=8000, count=20)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("redis updates read: %s", e)
            await asyncio.sleep(2)
            continue
        if not out:
            continue
        for _stream, messages in out:
            for msg_id, fields in messages:
                last_id = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
                raw = None
                for k, v in fields.items():
                    key = k.decode() if isinstance(k, bytes) else str(k)
                    if key == "data":
                        raw = v
                        break
                if raw is None:
                    continue
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                text = (
                    payload.get("summary")
                    or payload.get("message")
                    or payload.get("command")
                    or json.dumps(payload, default=str)[:500]
                )
                await manager.broadcast_json({"type": "coordinator_update", "payload": payload})
                await _tts_and_broadcast(manager, str(text), kind="update")


async def _voice_worker_heartbeat_loop() -> None:
    from shared.worker_registry_client import (
        default_instance_id,
        heartbeat_interval_sec,
        heartbeat_worker,
        register_worker,
    )

    if not os.getenv("CONTROL_PLANE_API_KEY", "").strip():
        return
    iid = default_instance_id()
    await register_worker(
        worker_type="voice",
        name=f"Voice ({iid})",
        meta={"redis_stream": STREAM_UPDATES, "pid": os.getpid()},
        instance_id=iid,
    )
    assert _manager is not None
    while True:
        await asyncio.sleep(heartbeat_interval_sec())
        n = await _manager.count_clients()
        await heartbeat_worker(
            worker_type="voice",
            meta={"websocket_clients": n, "pid": os.getpid()},
            instance_id=iid,
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _redis, _manager, _updates_task, _worker_hb_task
    _redis = Redis.from_url(REDIS_URL, decode_responses=False)
    _manager = ConnectionManager()
    _updates_task = asyncio.create_task(_redis_updates_loop(_manager))
    if os.getenv("CONTROL_PLANE_API_KEY", "").strip():
        _worker_hb_task = asyncio.create_task(_voice_worker_heartbeat_loop())
    yield
    if _worker_hb_task:
        _worker_hb_task.cancel()
        try:
            await _worker_hb_task
        except asyncio.CancelledError:
            pass
    if _updates_task:
        _updates_task.cancel()
        try:
            await _updates_task
        except asyncio.CancelledError:
            pass
    if _redis:
        await _redis.close()


app = FastAPI(title="JARVIS Voice", lifespan=lifespan)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    assert _manager is not None
    assert _redis is not None
    await _manager.connect(websocket)
    loop = asyncio.get_event_loop()
    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("type") != "websocket.receive":
                continue
            if "bytes" not in msg:
                continue
            audio = msg["bytes"]
            if not audio:
                continue

            await _manager.send_json(websocket, {"type": "status", "state": "thinking"})

            def _run_stt() -> str:
                fd, path = tempfile.mkstemp(suffix=".webm")
                os.close(fd)
                try:
                    with open(path, "wb") as f:
                        f.write(audio)
                    return _transcribe_file(path)
                finally:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass

            try:
                text = await loop.run_in_executor(None, _run_stt)
            except Exception as e:
                log.exception("stt: %s", e)
                await _manager.send_json(
                    websocket,
                    {"type": "error", "message": "Speech recognition failed."},
                )
                continue
            if not text:
                await _manager.send_json(
                    websocket,
                    {"type": "error", "message": "No speech detected."},
                )
                continue

            await _manager.send_json(websocket, {"type": "heard", "text": text})

            ws_key = id(websocket)
            tnorm = _norm_for_intent(text)

            async def _speak_local(reply: str, *, kind: str) -> None:
                await _manager.send_json(websocket, {"type": "reply", "text": reply})
                await _manager.send_json(websocket, {"type": "status", "state": "speaking"})
                try:
                    wav = await loop.run_in_executor(None, _tts_wav_bytes, reply)
                    b64 = base64.b64encode(wav).decode("ascii")
                    await _manager.send_json(
                        websocket,
                        {"type": "tts", "kind": kind, "text": reply, "audio_b64": b64},
                    )
                except Exception as e:
                    log.exception("tts voice reply: %s", e)
                await _manager.send_json(websocket, {"type": "status", "state": "idle"})

            if RE_VOICE_READ_AGAIN.search(tnorm):
                prev = _last_voice_reply.get(ws_key)
                if prev:
                    await _speak_local(prev, kind="repeat")
                    continue
                await _speak_local(
                    "I don't have anything to repeat yet. Ask what's happening, what needs my attention, "
                    "or what needs my approval.",
                    kind="repeat",
                )
                continue

            briefing_reply = await try_handle_voice_briefing(
                text,
                ws_key,
                control_plane_url=CONTROL_PLANE_URL,
                api_key=os.getenv("CONTROL_PLANE_API_KEY", ""),
            )
            if briefing_reply is not None:
                _last_voice_reply[ws_key] = briefing_reply
                await _speak_local(briefing_reply, kind="briefing")
                continue

            approval_reply = await try_handle_voice_approval(
                text,
                ws_key,
                control_plane_url=CONTROL_PLANE_URL,
                api_key=os.getenv("CONTROL_PLANE_API_KEY", ""),
            )
            if approval_reply is not None:
                _last_voice_reply[ws_key] = approval_reply
                await _speak_local(approval_reply, kind="approval")
                continue

            mission_id = await post_command_to_control_plane(text)

            if mission_id is not None:
                user_ollama = (
                    f"The user said: '{text}'. Mission ID {mission_id} has been created."
                )
            else:
                user_ollama = (
                    f"The user said: '{text}'. Acknowledge and confirm you understood."
                )

            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    r = await client.post(
                        f"{OLLAMA_BASE}/api/chat",
                        json={
                            "model": OLLAMA_MODEL,
                            "messages": [
                                {"role": "system", "content": OLLAMA_ACK_SYSTEM},
                                {"role": "user", "content": user_ollama},
                            ],
                            "stream": False,
                        },
                    )
                    r.raise_for_status()
                    body = r.json()
                    reply = (body.get("message") or {}).get("content") or ""
                    reply = re.sub(r"<\|[^>]+\|>", "", reply).strip()
            except Exception as e:
                log.exception("ollama: %s", e)
                await _manager.send_json(
                    websocket,
                    {"type": "error", "message": "Ollama request failed."},
                )
                continue

            await _manager.send_json(websocket, {"type": "reply", "text": reply})
            _last_voice_reply[id(websocket)] = reply
            await _manager.send_json(websocket, {"type": "status", "state": "speaking"})
            try:
                wav = await loop.run_in_executor(None, _tts_wav_bytes, reply)
                b64 = base64.b64encode(wav).decode("ascii")
                await _manager.send_json(
                    websocket,
                    {"type": "tts", "kind": "ollama", "text": reply, "audio_b64": b64},
                )
            except Exception as e:
                log.exception("tts: %s", e)
            await _manager.send_json(websocket, {"type": "status", "state": "idle"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.exception("websocket error: %s", e)
    finally:
        _forget_voice_session(id(websocket))
        await _manager.disconnect(websocket)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

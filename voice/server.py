"""
JARVIS Voice Server — FastAPI + WebSocket, faster-whisper STT, subprocess-isolated TTS, Redis streams.

MACHINE_CONFIG_REQUIRED: REDIS_URL, CONTROL_PLANE_URL, Whisper env; local .env beside this file.
UPSTREAM_DEPENDENCY: faster-whisper, pyttsx3 (one-shot worker only), and optional GPU — not pinned to CI here.
TRUTH_SOURCE: free-form utterances use ``POST /api/v1/intake``; replies come from the control-plane bundle (no cosmetic Ollama ack).
Voice TTS uses ``spoken_render`` condensation; the transcript still shows full ``reply.message``.

Specialized handlers (unchanged order): read that again → inbox → briefing → governed action → approval → **unified intake**.
"Read that again" repeats the last reply text and replays the last successful TTS payload (no regeneration).
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

from .approval_voice import forget_voice_approval_state, try_handle_voice_approval
from .briefing_voice import forget_voice_briefing_state, try_handle_voice_briefing
from .governed_action_voice import (
    forget_voice_governed_action_state,
    note_voice_command_mission,
    try_handle_governed_action_voice,
)
from .inbox_voice import forget_voice_inbox_state, try_handle_voice_inbox
from .intake_voice import post_voice_intake
from .last_spoken import (
    NO_AUDIO_REPEAT_HINT,
    LastSpokenTurn,
    normalize_last_voice_entry,
    ws_tts_message,
)
from .speech_mode import MODE_BROWSER_FIRST, normalize_speech_mode
from .spoken_render import generic_voice_spoken, shape_intake_voice_reply
from .tts_isolated import TTS_SYNTHESIS_TIMEOUT_SEC, synthesize_wav_isolated
from .voice_routing import MissionSubscriptionIndex

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jarvis.voice")

# Subprocess TTS budget (see ``tts_isolated``); override with JARVIS_VOICE_TTS_TIMEOUT_SEC.
TTS_WAV_TIMEOUT_SEC = TTS_SYNTHESIS_TIMEOUT_SEC

load_dotenv(Path(__file__).resolve().parent / ".env")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
# Override with CONTROL_PLANE_URL if the control plane listens elsewhere.
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8001").rstrip("/")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
if WHISPER_DEVICE == "cuda":
    WHISPER_COMPUTE = "float16"
else:
    WHISPER_COMPUTE = "int8"

STREAM_UPDATES = "jarvis.updates"

STATIC_DIR = Path(__file__).resolve().parent / "static"

_model = None
_redis: Redis | None = None
_manager = None
_updates_task: asyncio.Task | None = None
_worker_hb_task: asyncio.Task | None = None
_http_client: httpx.AsyncClient | None = None

# Last spoken reply per WebSocket for "read that again" (text + last successful TTS payload).
_last_voice_reply: dict[int, LastSpokenTurn | str] = {}

RE_VOICE_READ_AGAIN = re.compile(
    r"\b(read\s+that\s+again|repeat\s+(that|it|the\s+approval)|say\s+that\s+again)\b",
    re.I,
)

# Client may speak this locally (Web Speech API) when server WAV synthesis fails.
TTS_UNAVAILABLE_REASON = "tts_unavailable"
REPEAT_NO_AUDIO_REASON = "repeat_no_audio"
# ``tts`` JSON: ``delivery: "browser"`` means speak ``text`` locally; no ``audio_b64``.
TTS_DELIVERY_BROWSER = "browser"


def _tts_fallback_error_message() -> str:
    return (
        "Server speech synthesis failed or timed out; try local voice playback if offered below."
    )


def _norm_for_intent(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _forget_voice_session(ws_key: int) -> None:
    forget_voice_approval_state(ws_key)
    forget_voice_briefing_state(ws_key)
    forget_voice_inbox_state(ws_key)
    forget_voice_governed_action_state(ws_key)
    _last_voice_reply.pop(ws_key, None)


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel("base", device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)
    return _model


def _transcribe_file(path: str) -> str:
    model = _get_model()
    segments, _ = model.transcribe(path, language="en")
    return "".join(s.text for s in segments).strip()


def _short_sid(s: str | None) -> str:
    if not s:
        return "none"
    s = s.strip()
    if len(s) <= 12:
        return s
    return f"{s[:8]}…"


class VoiceConnectionManager:
    """WebSocket registry + per-connection mission subscriptions for routed updates/TTS."""

    def __init__(self) -> None:
        self._index = MissionSubscriptionIndex()
        self._sockets: dict[int, WebSocket] = {}
        self._surface_session: dict[int, str | None] = {}
        self._speech_mode: dict[int, str] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        ws: WebSocket,
        *,
        surface_session_id: str | None,
        thread_mission_id: str | None,
        speech_mode: str | None = None,
    ) -> int:
        await ws.accept()
        k = id(ws)
        mode = normalize_speech_mode(speech_mode)
        initial: set[str] = set()
        if thread_mission_id and str(thread_mission_id).strip():
            initial.add(str(thread_mission_id).strip())
        async with self._lock:
            self._sockets[k] = ws
            self._surface_session[k] = surface_session_id.strip() if surface_session_id else None
            self._speech_mode[k] = mode
            self._index.add_connection(k, initial)
        log.info(
            "voice_ws_registered key=%s surface_session=%s speech_mode=%s initial_mission_subs=%s",
            k,
            _short_sid(self._surface_session.get(k)),
            mode,
            len(initial),
        )
        return k

    def surface_session_for(self, ws_key: int) -> str | None:
        return self._surface_session.get(ws_key)

    def speech_mode_for(self, ws_key: int) -> str:
        """``browser_first`` (default) or ``server_preferred``."""
        return self._speech_mode.get(ws_key, MODE_BROWSER_FIRST)

    async def subscribe_mission(self, ws_key: int, mission_id: str) -> None:
        mid = str(mission_id).strip()
        if not mid:
            return
        async with self._lock:
            self._index.add_mission(ws_key, mid)
        log.info(
            "voice_mission_subscribed key=%s mission_id=%s total_subs=%s",
            ws_key,
            mid[:8] + "…" if len(mid) > 8 else mid,
            self._index.snapshot_mission_count(ws_key),
        )

    async def disconnect(self, ws: WebSocket) -> None:
        k = id(ws)
        async with self._lock:
            self._sockets.pop(k, None)
            self._surface_session.pop(k, None)
            self._speech_mode.pop(k, None)
            self._index.remove_connection(k)
        log.info("voice_ws_disconnected key=%s", k)

    async def send_json(self, ws: WebSocket, data: dict) -> None:
        await ws.send_json(data)

    async def websocket_targets_for_mission(self, mission_id: str) -> list[WebSocket]:
        mid = str(mission_id).strip()
        if not mid:
            return []
        async with self._lock:
            keys = self._index.connection_keys_for_mission(mid)
            out: list[WebSocket] = []
            for k in keys:
                ws = self._sockets.get(k)
                if ws is not None:
                    out.append(ws)
            return out

    async def count_clients(self) -> int:
        async with self._lock:
            return len(self._sockets)


async def _tts_to_websockets(
    manager: VoiceConnectionManager, websockets: list[WebSocket], text: str, *, kind: str
) -> None:
    if not text.strip() or not websockets:
        return
    line = text.strip()
    wav_clients: list[WebSocket] = []
    for ws in websockets:
        k = id(ws)
        if manager.speech_mode_for(k) == MODE_BROWSER_FIRST:
            msg = {
                "type": "tts",
                "kind": kind,
                "text": line,
                "delivery": TTS_DELIVERY_BROWSER,
            }
            try:
                await manager.send_json(ws, msg)
            except Exception as e:
                log.warning("voice_tts_send_failed: %s", e)
        else:
            wav_clients.append(ws)
    if not wav_clients:
        return
    try:
        wav = await synthesize_wav_isolated(line)
    except (asyncio.TimeoutError, RuntimeError, ValueError) as e:
        log.warning("voice_redis_tts_skipped: %s", e)
        for ws in wav_clients:
            try:
                await manager.send_json(
                    ws,
                    {
                        "type": "tts",
                        "kind": kind,
                        "text": line,
                        "delivery": TTS_DELIVERY_BROWSER,
                    },
                )
            except Exception as e2:
                log.warning("voice_tts_send_failed: %s", e2)
        return
    b64 = base64.b64encode(wav).decode("ascii")
    msg = {"type": "tts", "kind": kind, "text": line, "audio_b64": b64}
    for ws in wav_clients:
        try:
            await manager.send_json(ws, msg)
        except Exception as e:
            log.warning("voice_tts_send_failed: %s", e)


async def _redis_updates_loop(manager: VoiceConnectionManager) -> None:
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
                mid = str(payload.get("mission_id") or "").strip()
                if not mid:
                    log.warning(
                        "voice_redis_update_no_mission_id keys=%s",
                        list(payload.keys())[:20],
                    )
                    continue
                targets = await manager.websocket_targets_for_mission(mid)
                if not targets:
                    log.info(
                        "voice_redis_no_subscribers mission_id=%s",
                        (mid[:8] + "…") if len(mid) > 8 else mid,
                    )
                    continue
                tts_text = str(
                    payload.get("summary")
                    or payload.get("message")
                    or payload.get("command")
                    or json.dumps(payload, default=str)[:500]
                )
                upd = {"type": "coordinator_update", "payload": payload}
                for ws in targets:
                    try:
                        await manager.send_json(ws, upd)
                    except Exception as e:
                        log.warning("voice_coordinator_update_send_failed: %s", e)
                await _tts_to_websockets(manager, targets, tts_text, kind="update")


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
    global _redis, _manager, _updates_task, _worker_hb_task, _http_client
    _http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0),
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
    )
    _redis = Redis.from_url(REDIS_URL, decode_responses=False)
    _manager = VoiceConnectionManager()
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
    if _http_client:
        await _http_client.aclose()
        _http_client = None


app = FastAPI(title="JARVIS Voice", lifespan=lifespan)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    assert _manager is not None
    assert _redis is not None
    assert _http_client is not None
    qp = websocket.query_params
    surface_sid = (qp.get("surface_session_id") or "").strip() or None
    thread_mid = (qp.get("thread_mission_id") or "").strip() or None
    ws_key: int | None = None
    loop = asyncio.get_event_loop()
    try:
        speech_mode_q = (qp.get("speech_mode") or "").strip() or None
        ws_key = await _manager.connect(
            websocket,
            surface_session_id=surface_sid,
            thread_mission_id=thread_mid,
            speech_mode=speech_mode_q,
        )
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

            tnorm = _norm_for_intent(text)

            async def _replay_cached_tts(turn: LastSpokenTurn) -> None:
                """Resend last successful TTS bytes — no pyttsx3 (avoids Windows hangs on repeat)."""
                msg = ws_tts_message(turn, kind="repeat")
                if msg is None:
                    await _repeat_text_only_no_audio(turn)
                    return
                await _manager.send_json(
                    websocket,
                    {
                        "type": "reply",
                        "text": turn.display_text,
                        "spoken_text": turn.spoken_text,
                    },
                )
                await _manager.send_json(websocket, {"type": "status", "state": "speaking"})
                try:
                    await _manager.send_json(websocket, msg)
                finally:
                    try:
                        await _manager.send_json(websocket, {"type": "status", "state": "idle"})
                    except Exception as e2:
                        log.warning("voice status idle send failed: %s", e2)

            async def _repeat_text_only_no_audio(turn: LastSpokenTurn) -> None:
                await _manager.send_json(
                    websocket,
                    {
                        "type": "reply",
                        "text": turn.display_text,
                        "spoken_text": turn.spoken_text,
                    },
                )
                await _manager.send_json(
                    websocket,
                    {
                        "type": "error",
                        "message": NO_AUDIO_REPEAT_HINT,
                        "spoken_text": turn.spoken_text,
                        "reason": REPEAT_NO_AUDIO_REASON,
                    },
                )
                await _manager.send_json(websocket, {"type": "status", "state": "idle"})

            async def _speak_local(
                ws_key_inner: int,
                display_text: str,
                *,
                kind: str,
                spoken_text: str | None = None,
            ) -> None:
                spoken = (
                    spoken_text
                    if spoken_text is not None
                    else generic_voice_spoken(display_text, kind=kind)
                ).strip()
                if not spoken:
                    spoken = generic_voice_spoken(display_text, kind=kind).strip()
                await _manager.send_json(
                    websocket,
                    {
                        "type": "reply",
                        "text": display_text,
                        "spoken_text": spoken,
                    },
                )
                await _manager.send_json(websocket, {"type": "status", "state": "speaking"})
                try:
                    if _manager.speech_mode_for(ws_key_inner) == MODE_BROWSER_FIRST:
                        await _manager.send_json(
                            websocket,
                            {
                                "type": "tts",
                                "kind": kind,
                                "text": spoken,
                                "delivery": TTS_DELIVERY_BROWSER,
                            },
                        )
                        _last_voice_reply[ws_key_inner] = LastSpokenTurn(
                            display_text=display_text,
                            spoken_text=spoken,
                            kind=kind,
                            audio_b64=None,
                        )
                    else:
                        wav = await synthesize_wav_isolated(spoken)
                        b64 = base64.b64encode(wav).decode("ascii")
                        await _manager.send_json(
                            websocket,
                            {"type": "tts", "kind": kind, "text": spoken, "audio_b64": b64},
                        )
                        _last_voice_reply[ws_key_inner] = LastSpokenTurn(
                            display_text=display_text,
                            spoken_text=spoken,
                            kind=kind,
                            audio_b64=b64,
                        )
                except (asyncio.TimeoutError, RuntimeError) as e:
                    log.warning(
                        "tts voice reply failed (%s): kind=%s spoken_len=%s display_len=%s detail=%s",
                        type(e).__name__,
                        kind,
                        len(spoken),
                        len(display_text),
                        e,
                    )
                    _last_voice_reply[ws_key_inner] = LastSpokenTurn(
                        display_text=display_text,
                        spoken_text=spoken,
                        kind=kind,
                        audio_b64=None,
                    )
                    await _manager.send_json(
                        websocket,
                        {
                            "type": "error",
                            "message": _tts_fallback_error_message(),
                            "spoken_text": spoken,
                            "reason": TTS_UNAVAILABLE_REASON,
                        },
                    )
                except Exception as e:
                    log.exception("tts voice reply: %s", e)
                    _last_voice_reply[ws_key_inner] = LastSpokenTurn(
                        display_text=display_text,
                        spoken_text=spoken,
                        kind=kind,
                        audio_b64=None,
                    )
                    await _manager.send_json(
                        websocket,
                        {
                            "type": "error",
                            "message": _tts_fallback_error_message(),
                            "spoken_text": spoken,
                            "reason": TTS_UNAVAILABLE_REASON,
                        },
                    )
                finally:
                    try:
                        await _manager.send_json(websocket, {"type": "status", "state": "idle"})
                    except Exception as e2:
                        log.warning("voice status idle send failed: %s", e2)

            if RE_VOICE_READ_AGAIN.search(tnorm):
                prev = normalize_last_voice_entry(_last_voice_reply.get(ws_key))
                if prev and prev.display_text.strip():
                    if prev.audio_b64:
                        await _replay_cached_tts(prev)
                    else:
                        await _repeat_text_only_no_audio(prev)
                    continue
                await _speak_local(
                    ws_key,
                    "I don't have anything to repeat yet. Ask what's in your inbox, what's happening, "
                    "what needs my attention, or what needs my approval.",
                    kind="repeat",
                )
                continue

            inbox_reply = await try_handle_voice_inbox(
                text,
                ws_key,
                control_plane_url=CONTROL_PLANE_URL,
                api_key=os.getenv("CONTROL_PLANE_API_KEY", ""),
            )
            if inbox_reply is not None:
                await _speak_local(ws_key, inbox_reply, kind="inbox")
                continue

            briefing_reply = await try_handle_voice_briefing(
                text,
                ws_key,
                control_plane_url=CONTROL_PLANE_URL,
                api_key=os.getenv("CONTROL_PLANE_API_KEY", ""),
            )
            if briefing_reply is not None:
                await _speak_local(ws_key, briefing_reply, kind="briefing")
                continue

            governed_reply = await try_handle_governed_action_voice(
                text,
                ws_key,
                control_plane_url=CONTROL_PLANE_URL,
                api_key=os.getenv("CONTROL_PLANE_API_KEY", ""),
            )
            if governed_reply is not None:
                await _speak_local(ws_key, governed_reply, kind="governed_action")
                continue

            approval_reply = await try_handle_voice_approval(
                text,
                ws_key,
                control_plane_url=CONTROL_PLANE_URL,
                api_key=os.getenv("CONTROL_PLANE_API_KEY", ""),
            )
            if approval_reply is not None:
                await _speak_local(ws_key, approval_reply, kind="approval")
                continue

            surface = _manager.surface_session_for(ws_key)
            intake_res = await post_voice_intake(
                _http_client,
                control_plane_url=CONTROL_PLANE_URL,
                api_key=os.getenv("CONTROL_PLANE_API_KEY", ""),
                text=text,
                surface_session_id=surface,
                thread_mission_id=thread_mid,
            )
            if not intake_res.ok:
                err = intake_res.error_message or (
                    "I could not reach the Jarvis control plane. Check that it is running and configured."
                )
                await _manager.send_json(
                    websocket,
                    {"type": "error", "message": err},
                )
                await _speak_local(ws_key, err, kind="error")
                continue

            if intake_res.outcome == "mission_created" and intake_res.mission_id:
                note_voice_command_mission(ws_key, intake_res.mission_id)
                await _manager.subscribe_mission(ws_key, intake_res.mission_id)

            tts_kind = intake_res.reply_kind or "intake"
            shaped = shape_intake_voice_reply(
                message=intake_res.message,
                reply_kind=intake_res.reply_kind,
                outcome=intake_res.outcome,
                extras=intake_res.extras,
            )
            await _speak_local(
                ws_key,
                shaped.display_text,
                kind=tts_kind,
                spoken_text=shaped.spoken_text,
            )
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.exception("websocket error: %s", e)
    finally:
        if ws_key is not None:
            _forget_voice_session(ws_key)
        await _manager.disconnect(websocket)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

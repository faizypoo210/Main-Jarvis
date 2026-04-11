"""In-process real-time fan-out for SSE (same process as control plane API)."""

from app.realtime.hub import RealtimeHub, get_hub

__all__ = ["RealtimeHub", "get_hub"]

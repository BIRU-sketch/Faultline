"""In-memory event bus for live run progress streaming."""

from __future__ import annotations

import json
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunEventBus:
    """
    Lightweight per-run pub/sub for Server-Sent Events.

    Publishers (TestRunner) call publish().
    Subscribers (SSE endpoints) call subscribe() and iterate events.
    Events are retained briefly so late subscribers still receive recent history.
    """

    def __init__(self, history_limit: int = 200, subscriber_timeout: float = 0.75):
        self._lock = threading.Lock()
        self._subscribers: Dict[str, List[queue.Queue]] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = {}
        self._history_limit = history_limit
        self._subscriber_timeout = subscriber_timeout

    def publish(self, run_id: str, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
        event = {
            "type": event_type,
            "run_id": run_id,
            "ts": _utc_iso(),
            "payload": payload or {},
        }
        with self._lock:
            history = self._history.setdefault(run_id, [])
            history.append(event)
            if len(history) > self._history_limit:
                del history[0 : len(history) - self._history_limit]
            subscribers = list(self._subscribers.get(run_id, []))

        for q in subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                # Drop if a slow client backs up; keep the stream alive.
                pass

    def subscribe(self, run_id: str) -> Generator[Dict[str, Any], None, None]:
        """Yield historical events first, then live events until closed."""
        q: queue.Queue = queue.Queue(maxsize=256)
        with self._lock:
            self._subscribers.setdefault(run_id, []).append(q)
            history = list(self._history.get(run_id, []))

        for event in history:
            yield event

        try:
            while True:
                try:
                    event = q.get(timeout=self._subscriber_timeout)
                    yield event
                    if event.get("type") in ("run_completed", "run_failed", "run_cancelled"):
                        break
                except queue.Empty:
                    # Heartbeat so proxies and clients keep the connection open.
                    yield {"type": "heartbeat", "run_id": run_id, "ts": _utc_iso(), "payload": {}}
        finally:
            with self._lock:
                subs = self._subscribers.get(run_id, [])
                if q in subs:
                    subs.remove(q)
                if not subs and run_id in self._subscribers:
                    del self._subscribers[run_id]

    def clear(self, run_id: str) -> None:
        with self._lock:
            self._history.pop(run_id, None)
            self._subscribers.pop(run_id, None)


# Process-wide singleton used by runner + SSE endpoint
event_bus = RunEventBus()


def format_sse(event: Dict[str, Any]) -> str:
    """Serialize an event dict as a single SSE message."""
    event_type = event.get("type", "message")
    data = json.dumps(event, default=str)
    return f"event: {event_type}\ndata: {data}\n\n"

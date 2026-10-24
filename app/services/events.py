"""Minimal async in-process event bus.

Phase 2 emits domain events (e.g. ``NewPropertyIngested``) that Phase 3
consumers subscribe to — this keeps the ingestion pipeline decoupled from the
matching engine while still triggering it within the same millisecond.
"""

from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.logging import get_logger

logger = get_logger("app.events")

# Canonical event names -----------------------------------------------------
NEW_PROPERTY_INGESTED = "NewPropertyIngested"
PROPERTY_SHARED_TO_MLS = "PropertySharedToMls"
LICENSE_STATE_CHANGED = "LicenseStateChanged"

Handler = Callable[..., Any | Awaitable[Any]]


class EventBus:
    """A tiny publish/subscribe bus supporting async handlers."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler) -> Handler:
        self._subscribers[event].append(handler)
        return handler

    def unsubscribe(self, event: str, handler: Handler) -> None:
        if handler in self._subscribers.get(event, []):
            self._subscribers[event].remove(handler)

    def clear(self, event: str | None = None) -> None:
        """Drop all handlers for ``event`` (or the whole bus when ``None``)."""
        if event is None:
            self._subscribers.clear()
        else:
            self._subscribers.pop(event, None)

    def handlers_for(self, event: str) -> list[Handler]:
        return list(self._subscribers.get(event, []))

    async def emit(self, event: str, **payload: Any) -> None:
        """Invoke every handler; a failing handler never breaks the publisher."""
        for handler in self.handlers_for(event):
            try:
                result = handler(**payload)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:  # noqa: BLE001 - isolation is the point
                logger.warning(
                    "event handler failed for %s: %s", event, exc,
                    extra={"event": event},
                )


# Process-wide default bus.
event_bus = EventBus()

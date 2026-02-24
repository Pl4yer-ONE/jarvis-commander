"""
Max — Central Event Bus

Lightweight async pub/sub system for inter-subsystem communication.
Replaces file-based IPC (sentinel writing JSON to disk, dashboard reading it).

Usage:
    bus = EventBus()
    bus.subscribe("sentinel.camera", my_handler)
    await bus.publish("sentinel.camera", {"frame": ..., "ts": ...})

All handlers run as fire-and-forget tasks — a slow subscriber never blocks publishing.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

logger = logging.getLogger("max.event_bus")

Handler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    """Async pub/sub event bus for Max's subsystems."""

    def __init__(self, max_queue_size: int = 256):
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        self._state: dict[str, Any] = {}  # Latest snapshot per topic
        self._lock = asyncio.Lock()
        self._max_queue_size = max_queue_size

    def subscribe(self, topic: str, handler: Handler):
        """Register an async handler for a topic."""
        self._subscribers[topic].append(handler)
        logger.debug("Subscribed to '%s' (%d handlers)", topic, len(self._subscribers[topic]))

    def unsubscribe(self, topic: str, handler: Handler):
        """Remove a handler from a topic."""
        if handler in self._subscribers[topic]:
            self._subscribers[topic].remove(handler)

    async def publish(self, topic: str, data: dict[str, Any]):
        """Publish data to a topic. Stores latest state and notifies all subscribers."""
        async with self._lock:
            self._state[topic] = data

        for handler in self._subscribers.get(topic, []):
            try:
                asyncio.create_task(handler(data))
            except Exception as e:
                logger.error("Handler error on '%s': %s", topic, e)

    def get_state(self, topic: str) -> dict[str, Any] | None:
        """Get the latest published state for a topic (sync-safe read)."""
        return self._state.get(topic)

    def get_all_state(self) -> dict[str, Any]:
        """Get all latest state across all topics."""
        return dict(self._state)

    def clear(self):
        """Clear all state and subscribers."""
        self._subscribers.clear()
        self._state.clear()


# ── Module-level singleton ───────────────────────────────────

_bus: EventBus | None = None


def get_bus() -> EventBus:
    """Get or create the global event bus singleton."""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus

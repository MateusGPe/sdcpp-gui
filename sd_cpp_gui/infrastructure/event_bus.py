"""
Event Bus Module.
Implements a decoupled Publish-Subscribe pattern.
"""

import threading
from typing import Any, Callable, Dict, Optional

from sd_cpp_gui.infrastructure.logger import get_logger

logger = get_logger(__name__)


class EventBus:
    """
    Central event manager.
    """

    _subscribers: Dict[str, Dict[str, Callable[[Optional[Any]], None]]] = {}
    _lock = threading.RLock()

    @classmethod
    def subscribe(
        cls,
        channel: str,
        subscriber_id: str,
        callback: Callable[[Optional[Any]], None],
    ) -> None:
        """
        Registers a subscriber to a channel.

        Logic: Adds subscriber callback to channel.
        """
        if not channel or not subscriber_id or (not callable(callback)):
            logger.warning(
                "Invalid subscription attempt. Channel: %s, ID: %s",
                channel,
                subscriber_id,
            )
            return
        with cls._lock:
            if channel not in cls._subscribers:
                cls._subscribers[channel] = {}
            cls._subscribers[channel][subscriber_id] = callback

    @classmethod
    def unsubscribe(cls, channel: str, subscriber_id: str) -> None:
        """Removes a subscriber from a channel.

        Logic: Removes subscriber from channel."""
        with cls._lock:
            if channel in cls._subscribers:
                if cls._subscribers[channel].pop(subscriber_id, None):
                    pass
                if not cls._subscribers[channel]:
                    del cls._subscribers[channel]

    @classmethod
    def publish(cls, channel: str, payload: Optional[Any] = None) -> None:
        """
        Publishes an event to all subscribers of the channel.

        Logic: Invokes all callbacks for the channel.
        """
        with cls._lock:
            if channel not in cls._subscribers:
                return
            listeners = list(cls._subscribers[channel].items())
        for sub_id, callback in listeners:
            try:
                callback(payload)
            except Exception as exc:
                logger.error(
                    "Error processing event '%s' for subscriber '%s': %s",
                    channel,
                    sub_id,
                    exc,
                    exc_info=True,
                )

    @classmethod
    def clear_all(cls) -> None:
        """Removes all subscribers.

        Logic: Clears all subscriptions."""
        with cls._lock:
            cls._subscribers.clear()

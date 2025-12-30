import time
import threading
from collections import deque
from typing import Dict, List, Any, Optional


class MessageBus:
    """Thread-safe message bus with history retention and multiple consumer support."""

    def __init__(self, max_history: int = 500):
        self._lock = threading.RLock()
        self._messages: List[Dict[str, Any]] = []
        self._history: deque = deque(maxlen=max_history)
        self._message_id_counter = 0
        self._consumer_offsets: Dict[str, int] = {}  # Track read position per consumer

    def send(self, sender: str, msg_type: str, payload: Optional[Dict] = None,
             priority: int = 1, ts: Optional[float] = None) -> int:
        """Send a message to the bus. Returns message ID."""
        if ts is None:
            ts = time.time()

        with self._lock:
            self._message_id_counter += 1
            msg = {
                "id": self._message_id_counter,
                "type": msg_type,
                "sender": sender,
                "payload": payload or {},
                "priority": priority,
                "ts": ts
            }
            self._messages.append(msg)
            self._history.append(msg)
            return self._message_id_counter

    def read_all(self, consumer_id: str = "default", clear: bool = False) -> List[Dict[str, Any]]:
        """
        Read all messages since last read for this consumer.

        Args:
            consumer_id: Unique identifier for the consumer (allows multiple readers)
            clear: If True, clears ALL messages (legacy behavior)

        Returns:
            List of messages since last read by this consumer
        """
        with self._lock:
            if clear:
                # Legacy behavior - clear all messages
                msgs = self._messages.copy()
                self._messages.clear()
                return msgs

            # Get last read offset for this consumer
            last_offset = self._consumer_offsets.get(consumer_id, 0)

            # Find messages with ID > last_offset
            new_messages = [m for m in self._messages if m["id"] > last_offset]

            # Update consumer offset
            if self._messages:
                self._consumer_offsets[consumer_id] = self._messages[-1]["id"]

            return new_messages

    def read_recent(self, count: int = 50) -> List[Dict[str, Any]]:
        """Read the most recent N messages from history without affecting read state."""
        with self._lock:
            return list(self._history)[-count:]

    def get_history(self, since_id: int = 0) -> List[Dict[str, Any]]:
        """Get message history since a specific message ID."""
        with self._lock:
            return [m for m in self._history if m["id"] > since_id]

    def clear_old_messages(self, keep_recent: int = 100):
        """Clear old messages from active list, keeping recent ones."""
        with self._lock:
            if len(self._messages) > keep_recent:
                self._messages = self._messages[-keep_recent:]

    def reset(self):
        """Reset the message bus to initial state."""
        with self._lock:
            self._messages.clear()
            self._history.clear()
            self._message_id_counter = 0
            self._consumer_offsets.clear()
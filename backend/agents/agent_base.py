"""Base Agent class for disaster response agents."""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class Agent(ABC):
    """
    Abstract base class for all disaster response agents.
    Implements sense-decide-act cycle with message bus integration.
    """

    def __init__(self, name: str):
        self.name = name
        self.state: Dict[str, Any] = {}
        self._recent_messages: List[Dict] = []

    def sense(self, env, bus) -> Dict[str, Any]:
        """
        Gather observations from environment and message bus.

        Returns:
            Dictionary containing environment state and recent messages
        """
        obs = env.get_observation()

        # Also read recent messages from bus for inter-agent awareness
        # Use agent-specific consumer_id to allow multiple agents to read same messages
        self._recent_messages = bus.read_recent(count=20)

        # Filter messages from other agents
        other_agent_messages = [
            m for m in self._recent_messages
            if m.get("sender") != self.name
        ]

        # Add message context to observation
        obs["recent_messages"] = other_agent_messages
        obs["message_count"] = len(other_agent_messages)

        return obs

    @abstractmethod
    def decide(self, observation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Make decisions based on observations.

        Args:
            observation: Dictionary containing environment state and messages

        Returns:
            List of action/message dictionaries with format:
            {"type": "alert"|"plan"|"alloc"|..., "payload": {...}, "priority": int}
        """
        pass

    def act(self, env, bus) -> None:
        """
        Execute the sense-decide-act cycle.

        Args:
            env: Environment instance
            bus: MessageBus instance
        """
        obs = self.sense(env, bus)
        decisions = self.decide(obs) or []

        for d in decisions:
            msg_type = d.get("type", "info")
            payload = d.get("payload", {})
            priority = d.get("priority", 1)
            bus.send(self.name, msg_type, payload, priority)

    def get_state(self) -> Dict[str, Any]:
        """Get agent's internal state."""
        return {
            "name": self.name,
            "state": self.state.copy()
        }
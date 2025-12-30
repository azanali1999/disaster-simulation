"""Reflex Agent - Immediate reactive responses to environmental conditions."""
from typing import Dict, List, Any
from backend.agents.agent_base import Agent


class ReflexAgent(Agent):
    """
    Reflex agent that responds immediately to environmental stimuli.
    Active during 'response' phase only.
    """

    def __init__(self):
        super().__init__("ReflexAgent")
        self._last_alert_step = -1  # Avoid duplicate alerts in same step

    def decide(self, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Make reactive decisions based on current state."""
        msgs = []
        phase = obs.get("phase", "idle")
        time_step = obs.get("time_step", 0)

        # Only operate during response phase
        if phase != "response":
            return msgs

        # Skip if we already alerted this step
        if time_step == self._last_alert_step:
            return msgs

        if obs.get("disaster"):
            seismic_level = obs.get("seismic_level", 0)
            threshold = obs.get("params", {}).get("seismic_threshold", 0.5)

            # Determine severity based on seismic level
            if seismic_level >= threshold:
                severity = "critical" if seismic_level >= 0.8 else "high"
                message = f"ALERT: Seismic level {seismic_level:.2f} exceeds threshold {threshold:.2f} → Emergency evacuation!"
            else:
                severity = "medium"
                message = f"Monitoring: Seismic level {seismic_level:.2f} below threshold"

            # Check for aftershock
            if obs.get("aftershock"):
                severity = "critical"
                message = "AFTERSHOCK DETECTED! Take cover immediately!"

            payload = {
                "message": message,
                "severity": severity,
                "seismic_level": seismic_level,
                "aftershock": obs.get("aftershock", False),
                "time_step": time_step,
                "affected_areas": len(obs.get("affected_nodes", []))
            }

            priority = 10 if severity in ["critical", "high"] else 5
            msgs.append({"type": "alert", "payload": payload, "priority": priority})
            self._last_alert_step = time_step

        return msgs
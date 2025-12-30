"""Drone Reconnaissance Agent - Scouts affected areas before rescue operations."""
from typing import Dict, List, Any
from backend.agents.agent_base import Agent


class DroneReconAgent(Agent):
    """
    Drone reconnaissance agent that scouts affected areas.
    Operates during early response phase to identify victims and hazards.
    """

    # Reconnaissance parameters
    SCAN_RADIUS = 2  # Nodes scanned per drone per step
    VICTIMS_PER_SCAN = 3  # Victims identified per scan

    def __init__(self):
        super().__init__("DroneReconAgent")
        self._scanned_nodes = set()
        self._recon_complete = False
        self._recon_start_step = -1

    def decide(self, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Decide on reconnaissance actions."""
        msgs = []
        phase = obs.get("phase", "idle")
        time_step = obs.get("time_step", 0)

        # Only operate during response phase
        if phase != "response":
            self._scanned_nodes = set()
            self._recon_complete = False
            self._recon_start_step = -1
            return msgs

        # Track when recon started
        if self._recon_start_step < 0:
            self._recon_start_step = time_step

        resources = obs.get("resources", {})
        drones = resources.get("drones", 0)
        affected_nodes = obs.get("affected_nodes", [])

        if drones <= 0:
            return msgs

        # Calculate unscanned nodes
        affected_set = set(tuple(n) if isinstance(n, list) else n for n in affected_nodes)
        unscanned = affected_set - self._scanned_nodes

        if not unscanned and affected_nodes:
            if not self._recon_complete:
                self._recon_complete = True
                payload = {
                    "message": "Reconnaissance complete! All affected areas scanned.",
                    "total_scanned": len(self._scanned_nodes),
                    "time_step": time_step,
                    "recon_duration": time_step - self._recon_start_step
                }
                msgs.append({"type": "recon_complete", "payload": payload, "priority": 8})
            return msgs

        # Calculate nodes to scan this step
        nodes_per_step = drones * self.SCAN_RADIUS
        nodes_to_scan = list(unscanned)[:nodes_per_step]

        if nodes_to_scan:
            payload = {
                "message": f"Drones scanning {len(nodes_to_scan)} areas...",
                "nodes_scanned": nodes_to_scan,
                "drones_active": drones,
                "remaining_areas": len(unscanned) - len(nodes_to_scan),
                "time_step": time_step
            }
            msgs.append({"type": "recon", "payload": payload, "priority": 7})

        return msgs

    def act(self, env, bus) -> None:
        """Execute reconnaissance and update scanned areas."""
        obs = self.sense(env, bus)
        decisions = self.decide(obs) or []

        for d in decisions:
            payload = d.get("payload", {})

            if d.get("type") == "recon":
                nodes_scanned = payload.get("nodes_scanned", [])
                for node in nodes_scanned:
                    if isinstance(node, list):
                        self._scanned_nodes.add(tuple(node))
                    else:
                        self._scanned_nodes.add(node)

            # Send message to bus
            bus.send(self.name, d.get("type", "info"), payload, d.get("priority", 1))

    def get_position(self) -> Dict[str, Any]:
        """Return current drone positions for visualization."""
        if self._scanned_nodes:
            # Return the most recently scanned area as position
            last_scanned = list(self._scanned_nodes)[-1] if self._scanned_nodes else None
            if last_scanned:
                return {
                    "agent": self.name,
                    "type": "drone",
                    "x": last_scanned[0] if isinstance(last_scanned, tuple) else 0,
                    "y": last_scanned[1] if isinstance(last_scanned, tuple) else 0,
                    "status": "scanning" if not self._recon_complete else "complete"
                }
        return {
            "agent": self.name,
            "type": "drone",
            "x": 0,
            "y": 0,
            "status": "idle"
        }

    def is_recon_complete(self) -> bool:
        """Check if reconnaissance is complete."""
        return self._recon_complete


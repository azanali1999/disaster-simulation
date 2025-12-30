"""Orchestrator - Coordinates agent execution cycles."""
import threading
import random
import math
from typing import List, Dict, Any, Optional
from backend.agents.reflex_agent import ReflexAgent
from backend.agents.goal_agent import GoalBasedAgent
from backend.agents.utility_agent import UtilityAgent
from backend.agents.rebuild_agent import RebuildAgent
from backend.agents.drone_recon_agent import DroneReconAgent
from backend.agents.agent_base import Agent


class Orchestrator:
    """
    Thread-safe orchestrator for coordinating agent execution.
    Manages the sense-decide-act cycle for all agents.
    """

    def __init__(self, env, bus):
        self._lock = threading.RLock()
        self.env = env
        self.bus = bus
        self._paused = False
        self._cycle_count = 0

        # Initialize agents in priority order
        self.drone_recon = DroneReconAgent()  # Keep reference for recon status
        self.agents: List[Agent] = [
            ReflexAgent(),      # Priority 1: Immediate alerts
            self.drone_recon,   # Priority 2: Drone reconnaissance
            GoalBasedAgent(),   # Priority 3: Planning
            UtilityAgent(),     # Priority 4: Resource allocation
            RebuildAgent()      # Priority 5: Rebuild operations
        ]

        # Track active rescue units with their positions and movements
        self._active_units: List[Dict[str, Any]] = []
        self._unit_id_counter = 0

    def run_cycle(self) -> Dict[str, Any]:
        """
        Run one complete simulation cycle.

        Returns:
            Dictionary with cycle results
        """
        with self._lock:
            if self._paused:
                return {"status": "paused", "cycle": self._cycle_count}

            self._cycle_count += 1
            agent_results = []

            # Run sense/decide/act for each agent
            for agent in self.agents:
                try:
                    agent.act(self.env, self.bus)
                    agent_results.append({
                        "agent": agent.name,
                        "status": "success"
                    })
                except Exception as e:
                    agent_results.append({
                        "agent": agent.name,
                        "status": "error",
                        "error": str(e)
                    })

            # Advance environment
            self.env.update()

            # Clean up old messages periodically
            if self._cycle_count % 10 == 0:
                self.bus.clear_old_messages(keep_recent=100)

            return {
                "status": "completed",
                "cycle": self._cycle_count,
                "agent_results": agent_results
            }

    def pause(self) -> None:
        """Pause the orchestrator."""
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        """Resume the orchestrator."""
        with self._lock:
            self._paused = False

    def is_paused(self) -> bool:
        """Check if orchestrator is paused."""
        with self._lock:
            return self._paused

    def reset(self) -> None:
        """Reset the orchestrator and all agents."""
        with self._lock:
            self._cycle_count = 0
            self._paused = False
            self._active_units = []
            self._unit_id_counter = 0
            self.env.reset()
            self.bus.reset()

            # Reset agent states
            for agent in self.agents:
                agent.state = {}

    def get_status(self) -> Dict[str, Any]:
        """Get current orchestrator status."""
        with self._lock:
            return {
                "cycle_count": self._cycle_count,
                "paused": self._paused,
                "phase": self.env.phase,
                "agents": [agent.name for agent in self.agents]
            }

    def _spawn_rescue_unit(self, unit_type: str, start_node: Dict, target_node: Dict) -> Dict[str, Any]:
        """Create a new rescue unit with movement tracking."""
        self._unit_id_counter += 1
        return {
            "id": self._unit_id_counter,
            "type": unit_type,
            "status": "dispatched",
            "start_lat": start_node['lat'],
            "start_lng": start_node['lng'],
            "current_lat": start_node['lat'],
            "current_lng": start_node['lng'],
            "target_lat": target_node['lat'],
            "target_lng": target_node['lng'],
            "target_node_name": target_node['name'],
            "progress": 0.0,  # 0 to 1 movement progress
            "spawn_cycle": self._cycle_count,
        }

    def _update_unit_positions(self) -> None:
        """Update all active unit positions based on their movement progress."""
        move_speed = 0.15  # Progress per cycle (adjust for animation speed)

        units_to_remove = []
        for unit in self._active_units:
            if unit['status'] == 'dispatched':
                unit['progress'] = min(1.0, unit['progress'] + move_speed)

                # Interpolate position
                unit['current_lat'] = unit['start_lat'] + (unit['target_lat'] - unit['start_lat']) * unit['progress']
                unit['current_lng'] = unit['start_lng'] + (unit['target_lng'] - unit['start_lng']) * unit['progress']

                if unit['progress'] >= 1.0:
                    unit['status'] = 'responding'

            elif unit['status'] == 'responding':
                # Stay at target for a few cycles, then mark for return or remove
                cycles_at_target = self._cycle_count - unit['spawn_cycle'] - 7
                if cycles_at_target > 5:
                    unit['status'] = 'returning'
                    # Swap start and target for return journey
                    unit['start_lat'], unit['target_lat'] = unit['target_lat'], unit['start_lat']
                    unit['start_lng'], unit['target_lng'] = unit['target_lng'], unit['start_lng']
                    unit['progress'] = 0.0

            elif unit['status'] == 'returning':
                unit['progress'] = min(1.0, unit['progress'] + move_speed)
                unit['current_lat'] = unit['start_lat'] + (unit['target_lat'] - unit['start_lat']) * unit['progress']
                unit['current_lng'] = unit['start_lng'] + (unit['target_lng'] - unit['start_lng']) * unit['progress']

                if unit['progress'] >= 1.0:
                    units_to_remove.append(unit)

        # Remove completed units
        for unit in units_to_remove:
            self._active_units.remove(unit)

    def _manage_rescue_units(self, obs: Dict) -> None:
        """Manage spawning and lifecycle of rescue units based on simulation state."""
        nodes = obs.get("nodes", [])
        phase = obs.get("phase", "idle")
        resources = obs.get("resources", {})
        affected_nodes = obs.get("affected_nodes", [])

        if not nodes:
            return

        # Get command center (PDMA - id 26)
        command_center = next((n for n in nodes if n['id'] == 26), nodes[0])
        node_map = {n['id']: n for n in nodes}

        # Cap active units based on available resources
        max_ambulances = resources.get("ambulances", 0)
        max_drones = resources.get("drones", 0)
        max_medical = resources.get("medical_kits", 0) // 5  # 1 team per 5 kits
        max_repair = resources.get("repair_crews", 0)

        current_ambulances = sum(1 for u in self._active_units if u['type'] == 'ambulance')
        current_drones = sum(1 for u in self._active_units if u['type'] == 'drone')
        current_medical = sum(1 for u in self._active_units if u['type'] == 'medical')
        current_repair = sum(1 for u in self._active_units if u['type'] == 'repair_crew')

        if phase == "response" and affected_nodes:
            # Spawn ambulances
            if current_ambulances < min(max_ambulances, 3) and self._cycle_count % 2 == 0:
                target_id = random.choice(affected_nodes)
                if target_id in node_map:
                    unit = self._spawn_rescue_unit("ambulance", command_center, node_map[target_id])
                    self._active_units.append(unit)

            # Spawn drones (faster, spawn more frequently)
            if current_drones < min(max_drones, 4) and self._cycle_count % 3 == 0:
                target_id = random.choice(affected_nodes)
                if target_id in node_map:
                    unit = self._spawn_rescue_unit("drone", command_center, node_map[target_id])
                    self._active_units.append(unit)

            # Spawn medical teams
            if current_medical < min(max_medical, 2) and self._cycle_count % 4 == 0:
                # Medical teams go to high-population areas
                pop_affected = [(node_map[nid], node_map[nid].get('population', 0))
                                for nid in affected_nodes if nid in node_map]
                if pop_affected:
                    pop_affected.sort(key=lambda x: x[1], reverse=True)
                    target = pop_affected[0][0]
                    unit = self._spawn_rescue_unit("medical", command_center, target)
                    self._active_units.append(unit)

        elif phase == "rebuild":
            # Spawn repair crews for blocked roads
            blocked_edges = [e for e in obs.get("edges", []) if e.get("blocked")]
            if current_repair < min(max_repair, len(blocked_edges)) and self._cycle_count % 3 == 0:
                if blocked_edges:
                    edge = random.choice(blocked_edges)
                    from_node = node_map.get(edge['from'])
                    to_node = node_map.get(edge['to'])
                    if from_node and to_node:
                        # Target is midpoint of the blocked road
                        mid_node = {
                            'id': -1,
                            'name': f"{from_node['name']} - {to_node['name']} Road",
                            'lat': (from_node['lat'] + to_node['lat']) / 2,
                            'lng': (from_node['lng'] + to_node['lng']) / 2,
                        }
                        unit = self._spawn_rescue_unit("repair_crew", command_center, mid_node)
                        self._active_units.append(unit)

    def get_agent_positions(self) -> List[Dict[str, Any]]:
        """
        Get current positions of active agents and rescue units for visualization.
        Returns both static coordinator positions and animated rescue units.
        """
        with self._lock:
            positions = []
            obs = self.env.get_observation()
            nodes = obs.get("nodes", [])
            phase = obs.get("phase", "idle")

            if not nodes or phase == "idle":
                self._active_units = []  # Clear units when idle
                return positions

            # Get command center (PDMA - id 26)
            command_center = next((n for n in nodes if n['id'] == 26), nodes[0])

            # Add static coordinator positions
            positions.append({
                "agent": "PDMA_Coordinator",
                "type": "coordinator",
                "lat": command_center['lat'],
                "lng": command_center['lng'],
                "status": "coordinating",
                "is_static": True
            })

            if phase == "response":
                positions.append({
                    "agent": "GoalAgent_Planner",
                    "type": "planner",
                    "lat": command_center['lat'] + 0.005,
                    "lng": command_center['lng'] + 0.005,
                    "status": "planning_routes",
                    "is_static": True
                })

                # Add drone reconnaissance positions
                drone_pos = self.drone_recon.get_position()
                if drone_pos:
                    # Position drones near affected areas
                    affected_nodes = obs.get("affected_nodes", [])
                    if affected_nodes:
                        for i, affected in enumerate(affected_nodes[:3]):  # Show up to 3 drones
                            affected_node = next((n for n in nodes if n['id'] == affected), None)
                            if affected_node:
                                positions.append({
                                    "agent": f"Drone_Recon_{i+1}",
                                    "type": "drone",
                                    "lat": affected_node['lat'] + 0.002 * (i - 1),
                                    "lng": affected_node['lng'] + 0.002 * (i - 1),
                                    "status": drone_pos.get("status", "scanning"),
                                    "is_static": False
                                })

            # Update and spawn rescue units
            self._manage_rescue_units(obs)
            self._update_unit_positions()

            # Convert active units to positions with movement data
            for unit in self._active_units:
                positions.append({
                    "agent": f"{unit['type'].replace('_', ' ').title()}_{unit['id']}",
                    "type": unit['type'],
                    "lat": unit['current_lat'],
                    "lng": unit['current_lng'],
                    "status": unit['status'],
                    "target_node": unit['target_node_name'],
                    "progress": unit['progress'],
                    "is_static": False,
                    # Include path info for drawing travel routes
                    "path": {
                        "start_lat": unit['start_lat'],
                        "start_lng": unit['start_lng'],
                        "target_lat": unit['target_lat'],
                        "target_lng": unit['target_lng'],
                    } if unit['status'] in ['dispatched', 'returning'] else None
                })

            return positions
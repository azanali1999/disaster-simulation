import random
import threading
from typing import Dict, Any, Optional


class Environment:
    """Thread-safe disaster simulation environment."""

    def __init__(self):
        self._lock = threading.RLock()
        self.time_step = 0
        self.scenario = None
        self.disaster = False
        # phases: 'idle' | 'response' | 'rebuild' | 'recovered'
        self.phase = 'idle'
        self.victims = 0
        self.victims_saved = 0  # Track total victims saved
        self.seismic_level = 0.0
        self.aftershock = False
        self.roads_blocked = False
        # set default resources; will be randomized on trigger
        self.resources = {
            "ambulances": 5,
            "drones": 3,
            "medical_kits": 40,
            "repair_crews": 2,
            "food_packs": 50,
        }
        # keep a snapshot of initial resources to restore after recovery
        self.initial_resources = dict(self.resources)
        self.resources_used = {k: 0 for k in self.resources}  # Track resources consumed
        self.rebuild_progress = 0.0
        self.cooldown_counter = 0
        self.params = {
            "seismic_threshold": 0.5,
            "aftershock_factor": 0.3,
            "road_block_chance": 0.4,
            "rebuild_required": 100,
            "rebuild_factor_per_crew": 2.0
        }

        # Statistics tracking
        self.stats = {
            "total_victims_initial": 0,
            "victims_saved": 0,
            "disasters_completed": 0,
            "total_time_steps": 0,
        }

        # Karachi graph representation: detailed nodes (key locations) and edges (roads/connections)
        # Scale: Approximately 1 node per 1 million people or major area
        # Total pop ~20M, so ~20 major nodes, but adding sub-areas for detail
        self.nodes = [
            # District Centers (High-level)
            {"id": 0, "name": "Karachi Central", "lat": 24.8607, "lng": 67.0104, "population": 3822325, "type": "district_center", "infrastructure": 0.8, "vulnerability": {"earthquake": 1.2, "flood": 0.9, "wildfire": 0.5}},
            {"id": 1, "name": "Karachi East", "lat": 24.8800, "lng": 67.0600, "population": 3921742, "type": "district_center", "infrastructure": 0.7, "vulnerability": {"earthquake": 1.1, "flood": 1.0, "wildfire": 0.6}},
            {"id": 2, "name": "Karachi West", "lat": 24.8200, "lng": 66.9500, "population": 2679380, "type": "district_center", "infrastructure": 0.6, "vulnerability": {"earthquake": 1.0, "flood": 1.1, "wildfire": 0.7}},
            {"id": 3, "name": "Karachi South", "lat": 24.8200, "lng": 67.0300, "population": 2329764, "type": "district_center", "infrastructure": 0.75, "vulnerability": {"earthquake": 1.1, "flood": 1.2, "wildfire": 0.5}},
            {"id": 4, "name": "Malir", "lat": 24.9500, "lng": 67.2000, "population": 2432248, "type": "district_center", "infrastructure": 0.5, "vulnerability": {"earthquake": 0.9, "flood": 1.3, "wildfire": 0.8}},
            {"id": 5, "name": "Korangi", "lat": 24.8200, "lng": 67.1200, "population": 3128971, "type": "district_center", "infrastructure": 0.65, "vulnerability": {"earthquake": 1.0, "flood": 1.1, "wildfire": 0.6}},
            {"id": 6, "name": "Kemari", "lat": 24.7800, "lng": 66.9500, "population": 2068451, "type": "district_center", "infrastructure": 0.6, "vulnerability": {"earthquake": 1.0, "flood": 1.4, "wildfire": 0.7}},
            # Residential Areas
            {"id": 7, "name": "Saddar Residential", "lat": 24.8600, "lng": 67.0100, "population": 500000, "type": "residential", "infrastructure": 0.7, "vulnerability": {"earthquake": 1.2, "flood": 0.8, "wildfire": 0.6}},
            {"id": 8, "name": "Lyari Residential", "lat": 24.8500, "lng": 66.9900, "population": 600000, "type": "residential", "infrastructure": 0.5, "vulnerability": {"earthquake": 1.3, "flood": 1.0, "wildfire": 0.7}},
            {"id": 9, "name": "Clifton Residential", "lat": 24.8100, "lng": 67.0300, "population": 400000, "type": "residential", "infrastructure": 0.8, "vulnerability": {"earthquake": 1.0, "flood": 1.4, "wildfire": 0.5}},
            {"id": 10, "name": "Gulshan-e-Iqbal Residential", "lat": 24.9200, "lng": 67.0800, "population": 800000, "type": "residential", "infrastructure": 0.8, "vulnerability": {"earthquake": 1.1, "flood": 0.9, "wildfire": 0.6}},
            {"id": 11, "name": "Orangi Town Residential", "lat": 24.9500, "lng": 66.9800, "population": 1000000, "type": "residential", "infrastructure": 0.4, "vulnerability": {"earthquake": 1.3, "flood": 1.2, "wildfire": 0.8}},
            {"id": 12, "name": "North Nazimabad Residential", "lat": 24.9300, "lng": 67.0400, "population": 700000, "type": "residential", "infrastructure": 0.6, "vulnerability": {"earthquake": 1.1, "flood": 1.0, "wildfire": 0.7}},
            # Commercial Areas (Markets, Offices)
            {"id": 13, "name": "Saddar Market", "lat": 24.8550, "lng": 67.0150, "population": 100000, "type": "commercial", "infrastructure": 0.9, "vulnerability": {"earthquake": 1.2, "flood": 0.7, "wildfire": 0.4}},
            {"id": 14, "name": "Burns Road Offices", "lat": 24.8650, "lng": 67.0050, "population": 50000, "type": "commercial", "infrastructure": 0.8, "vulnerability": {"earthquake": 1.1, "flood": 0.8, "wildfire": 0.5}},
            {"id": 15, "name": "Tariq Road Market", "lat": 24.8750, "lng": 67.0250, "population": 150000, "type": "commercial", "infrastructure": 0.7, "vulnerability": {"earthquake": 1.0, "flood": 0.9, "wildfire": 0.6}},
            {"id": 16, "name": "Gulshan-e-Iqbal Commercial", "lat": 24.9150, "lng": 67.0750, "population": 200000, "type": "commercial", "infrastructure": 0.8, "vulnerability": {"earthquake": 1.1, "flood": 0.8, "wildfire": 0.5}},
            {"id": 17, "name": "Korangi Industrial Area", "lat": 24.8250, "lng": 67.1250, "population": 300000, "type": "industrial", "infrastructure": 0.6, "vulnerability": {"earthquake": 1.0, "flood": 1.1, "wildfire": 0.8}},
            # Landmarks
            {"id": 18, "name": "Jinnah International Airport", "lat": 24.9065, "lng": 67.1605, "population": 0, "type": "landmark", "infrastructure": 0.9, "vulnerability": {"earthquake": 1.0, "flood": 0.8, "wildfire": 0.4}},
            {"id": 19, "name": "Port of Karachi", "lat": 24.7800, "lng": 66.9700, "population": 0, "type": "landmark", "infrastructure": 0.8, "vulnerability": {"earthquake": 1.1, "flood": 1.5, "wildfire": 0.6}},
            # Public Services
            {"id": 20, "name": "Jinnah Postgraduate Medical Centre", "lat": 24.8600, "lng": 67.0100, "population": 0, "type": "public_service", "infrastructure": 0.9, "vulnerability": {"earthquake": 1.0, "flood": 0.7, "wildfire": 0.3}},
            {"id": 21, "name": "Civil Hospital Karachi", "lat": 24.8500, "lng": 67.0200, "population": 0, "type": "public_service", "infrastructure": 0.8, "vulnerability": {"earthquake": 1.1, "flood": 0.8, "wildfire": 0.4}},
            {"id": 22, "name": "Aga Khan Hospital", "lat": 24.8800, "lng": 67.0600, "population": 0, "type": "public_service", "infrastructure": 0.95, "vulnerability": {"earthquake": 0.9, "flood": 0.6, "wildfire": 0.2}},
            {"id": 23, "name": "Fire Station Clifton", "lat": 24.8100, "lng": 67.0250, "population": 0, "type": "public_service", "infrastructure": 0.8, "vulnerability": {"earthquake": 1.0, "flood": 1.0, "wildfire": 0.5}},
            {"id": 24, "name": "Fire Station Korangi", "lat": 24.8200, "lng": 67.1150, "population": 0, "type": "public_service", "infrastructure": 0.7, "vulnerability": {"earthquake": 1.1, "flood": 1.1, "wildfire": 0.6}},
            {"id": 25, "name": "Fire Station Malir", "lat": 24.9400, "lng": 67.1900, "population": 0, "type": "public_service", "infrastructure": 0.6, "vulnerability": {"earthquake": 0.9, "flood": 1.2, "wildfire": 0.7}},
            {"id": 26, "name": "Provincial Disaster Management Authority (PDMA)", "lat": 24.8600, "lng": 67.0000, "population": 0, "type": "public_service", "infrastructure": 0.9, "vulnerability": {"earthquake": 0.8, "flood": 0.7, "wildfire": 0.3}},
        ]
        self.edges = [
            # Connections between district centers
            {"from": 0, "to": 1, "distance": 5.0, "type": "highway", "blocked": False},  # Central to East
            {"from": 0, "to": 2, "distance": 7.0, "type": "highway", "blocked": False},  # Central to West
            {"from": 0, "to": 3, "distance": 4.0, "type": "road", "blocked": False},    # Central to South
            {"from": 1, "to": 4, "distance": 15.0, "type": "highway", "blocked": False}, # East to Malir
            {"from": 1, "to": 5, "distance": 6.0, "type": "road", "blocked": False},    # East to Korangi
            {"from": 2, "to": 6, "distance": 5.0, "type": "road", "blocked": False},    # West to Kemari
            {"from": 3, "to": 6, "distance": 8.0, "type": "highway", "blocked": False}, # South to Kemari
            {"from": 4, "to": 5, "distance": 20.0, "type": "highway", "blocked": False}, # Malir to Korangi
            # Connections to residential areas
            {"from": 0, "to": 7, "distance": 1.0, "type": "road", "blocked": False},    # Central to Saddar Residential
            {"from": 0, "to": 8, "distance": 2.0, "type": "road", "blocked": False},    # Central to Lyari Residential
            {"from": 3, "to": 9, "distance": 1.0, "type": "road", "blocked": False},    # South to Clifton Residential
            {"from": 1, "to": 10, "distance": 3.0, "type": "road", "blocked": False},   # East to Gulshan Residential
            {"from": 0, "to": 11, "distance": 10.0, "type": "highway", "blocked": False}, # Central to Orangi Residential
            {"from": 1, "to": 12, "distance": 5.0, "type": "road", "blocked": False},   # East to North Nazimabad Residential
            # Connections to commercial areas
            {"from": 0, "to": 13, "distance": 0.5, "type": "road", "blocked": False},   # Central to Saddar Market
            {"from": 0, "to": 14, "distance": 1.0, "type": "road", "blocked": False},   # Central to Burns Road Offices
            {"from": 0, "to": 15, "distance": 2.0, "type": "road", "blocked": False},   # Central to Tariq Road Market
            {"from": 1, "to": 16, "distance": 2.0, "type": "road", "blocked": False},   # East to Gulshan Commercial
            {"from": 5, "to": 17, "distance": 1.0, "type": "road", "blocked": False},   # Korangi to Industrial Area
            # Connections to landmarks
            {"from": 0, "to": 18, "distance": 12.0, "type": "highway", "blocked": False}, # Central to Airport
            {"from": 1, "to": 18, "distance": 8.0, "type": "road", "blocked": False},     # East to Airport
            {"from": 6, "to": 19, "distance": 2.0, "type": "road", "blocked": False},     # Kemari to Port
            # Connections to public services
            {"from": 0, "to": 20, "distance": 0.5, "type": "road", "blocked": False},    # Central to JPMC
            {"from": 0, "to": 21, "distance": 1.0, "type": "road", "blocked": False},    # Central to Civil Hospital
            {"from": 1, "to": 22, "distance": 1.0, "type": "road", "blocked": False},    # East to Aga Khan
            {"from": 3, "to": 23, "distance": 0.5, "type": "road", "blocked": False},    # South to Fire Clifton
            {"from": 5, "to": 24, "distance": 0.5, "type": "road", "blocked": False},    # Korangi to Fire Korangi
            {"from": 4, "to": 25, "distance": 1.0, "type": "road", "blocked": False},    # Malir to Fire Malir
            {"from": 0, "to": 26, "distance": 1.0, "type": "road", "blocked": False},    # Central to PDMA
            # Additional connections for density
            {"from": 7, "to": 13, "distance": 0.5, "type": "road", "blocked": False},    # Saddar Residential to Market
            {"from": 9, "to": 23, "distance": 0.5, "type": "road", "blocked": False},    # Clifton Residential to Fire
            {"from": 10, "to": 16, "distance": 1.0, "type": "road", "blocked": False},   # Gulshan Residential to Commercial
        ]
        self.affected_nodes = []  # List of affected node ids
        self.affected_edges = []  # List of affected edge indices



    def trigger_disaster(self, scenario: str = "earthquake", intensity: float = 1.0,
                         resources: Optional[Dict[str, int]] = None) -> None:
        """Trigger a new disaster scenario with thread safety."""
        with self._lock:
            # scenario: earthquake|flood|wildfire
            self.scenario = scenario
            self.disaster = True
            self.phase = 'response'
            self.time_step = 0
            self.victims_saved = 0
            self.seismic_level = max(0.0, min(1.0, float(intensity)))

            # Determine affected nodes based on scenario
            self.affected_nodes = []
            if scenario == "earthquake":
                # Earthquakes affect all nodes
                self.affected_nodes = list(range(len(self.nodes)))
            elif scenario == "flood":
                # Floods more likely in coastal/residential nodes
                coastal_ids = [3, 4, 6, 19, 9, 8, 11]
                for node in self.nodes:
                    if node['id'] in coastal_ids or random.random() < 0.3:
                        self.affected_nodes.append(node['id'])
            elif scenario == "wildfire":
                # Wildfires in drier/commercial nodes
                dry_ids = [2, 4, 6, 17]
                for node in self.nodes:
                    if node['id'] in dry_ids or random.random() < 0.2:
                        self.affected_nodes.append(node['id'])
            else:
                # Default: random selection
                self.affected_nodes = [node['id'] for node in self.nodes if random.random() < 0.7]

            # Affected edges: edges connected to affected nodes
            self.affected_edges = []
            for idx, edge in enumerate(self.edges):
                if edge['from'] in self.affected_nodes or edge['to'] in self.affected_nodes:
                    self.affected_edges.append(idx)
                    # Block some edges based on type and intensity
                    block_chance = 0.2 if edge['type'] == 'road' else 0.1
                    if random.random() < block_chance * self.seismic_level:
                        edge['blocked'] = True

            # Set roads_blocked if any edge is blocked
            self.roads_blocked = any(edge['blocked'] for edge in self.edges)

            # Calculate victims based on affected nodes
            self.victims = 0
            for node_id in self.affected_nodes:
                node = self.nodes[node_id]
                vuln = node['vulnerability'].get(scenario, 1.0)
                base_victims = int(node['population'] * 0.01 * self.seismic_level * vuln)
                self.victims += base_victims

            # Ensure minimum victims
            self.victims = max(10, self.victims)

            # Track initial victims for statistics
            self.stats["total_victims_initial"] = self.victims

            # If resources dict provided, use it (validate and fill defaults); otherwise randomize by scenario
            if resources and isinstance(resources, dict):
                # use existing keys as defaults, override with provided values (coerce to int and clamp >=0)
                new_res = dict(self.resources)
                for k, v in resources.items():
                    if k in new_res:
                        try:
                            new_res[k] = max(0, int(v))
                        except Exception:
                            # ignore invalid values and keep default
                            pass
                self.resources = new_res
            else:
                # randomize resources at start (ranges can be tuned)
                if scenario == "earthquake":
                    self.resources["ambulances"] = random.randint(3, 8)
                    self.resources["drones"] = random.randint(1, 4)
                    self.resources["medical_kits"] = random.randint(20, 80)
                    self.resources["repair_crews"] = random.randint(1, 4)
                    self.resources["food_packs"] = random.randint(30, 100)
                elif scenario == "flood":
                    self.resources["ambulances"] = random.randint(2, 6)
                    self.resources["drones"] = random.randint(2, 6)
                    self.resources["medical_kits"] = random.randint(15, 60)
                    self.resources["repair_crews"] = random.randint(2, 6)
                    self.resources["food_packs"] = random.randint(40, 120)
                elif scenario == "wildfire":
                    self.resources["ambulances"] = random.randint(1, 4)
                    self.resources["drones"] = random.randint(3, 8)
                    self.resources["medical_kits"] = random.randint(10, 40)
                    self.resources["repair_crews"] = random.randint(3, 8)
                    self.resources["food_packs"] = random.randint(20, 80)
                else:
                    # generic randomization
                    for k in self.resources.keys():
                        self.resources[k] = max(0, int(random.randint(1, 10) * (1 + self.seismic_level)))

            # set initial snapshot and reset resources_used AFTER setting resources
            self.initial_resources = dict(self.resources)
            self.resources_used = {k: 0 for k in self.resources}

    def get_observation(self) -> Dict[str, Any]:
        """Return a thread-safe read-only snapshot for agents."""
        with self._lock:
            return {
                "time_step": self.time_step,
                "scenario": self.scenario,
                "disaster": self.disaster,
                "phase": self.phase,
                "rebuild_progress": float(self.rebuild_progress),
                "cooldown_counter": int(self.cooldown_counter),
                "victims": int(self.victims),
                "victims_saved": int(self.victims_saved),
                "seismic_level": float(self.seismic_level),
                "aftershock": bool(self.aftershock),
                "roads_blocked": bool(self.roads_blocked),
                "resources": {k: int(v) for k, v in self.resources.items()},
                "resources_used": {k: int(v) for k, v in self.resources_used.items()},
                "initial_resources": {k: int(v) for k, v in self.initial_resources.items()},
                "params": dict(self.params),
                "nodes": [node.copy() for node in self.nodes],
                "edges": [edge.copy() for edge in self.edges],
                "affected_nodes": self.affected_nodes.copy(),
                "affected_edges": self.affected_edges.copy(),
                "stats": dict(self.stats)
            }

    def get_grid_text(self):
        """Return a text representation of the graph for visualization."""
        text = "Nodes:\n"
        for node in self.nodes:
            status = "Affected" if node['id'] in self.affected_nodes else "Normal"
            text += f"{node['id']}: {node['name']} ({node['type']}) - Pop: {node['population']}, Status: {status}\n"
        text += "\nEdges:\n"
        for edge in self.edges:
            from_name = self.nodes[edge['from']]['name']
            to_name = self.nodes[edge['to']]['name']
            status = "Blocked" if edge['blocked'] else "Open"
            text += f"{from_name} -> {to_name} ({edge['type']}, {edge['distance']}km) - {status}\n"
        return text

    def update(self) -> None:
        """Advance the environment one time-step and evolve state with thread safety."""
        with self._lock:
            # if nothing active, remain idle
            if self.phase == 'idle':
                return

            self.time_step += 1
            self.stats["total_time_steps"] += 1

            # RESPONSE PHASE: active disaster response
            if self.phase == 'response':
                # aftershock probability increases with seismic_level
                self.aftershock = random.random() < (self.params["aftershock_factor"] * (0.5 + self.seismic_level))

                # roads can become blocked or cleared depending on randomness and aftershocks
                block_chance = self.params["road_block_chance"] + 0.2 * self.seismic_level + (0.2 if self.aftershock else 0)
                self.roads_blocked = random.random() < block_chance

                # natural reduction in seismic level over time
                decay = random.random() * 0.1
                self.seismic_level = max(0.0, self.seismic_level - decay)

                # small chance of new victims appearing (secondary collapses) if aftershock
                if self.aftershock and random.random() < 0.2:
                    new_victims = random.randint(1, int(10 * (0.5 + self.seismic_level)))
                    self.victims += new_victims

                # transition to rebuild when victims cleared and no recent aftershock
                if self.victims <= 0 and not self.aftershock:
                    self.phase = 'rebuild'
                    self.rebuild_progress = 0.0
                    # Update statistics
                    self.stats["victims_saved"] = self.victims_saved

            # REBUILD PHASE: use repair crews / resources to repair infrastructure
            elif self.phase == 'rebuild':
                # rebuild progress depends on number of repair crews and drones (support)
                crews = max(0, int(self.resources.get('repair_crews', 0)))
                drones = max(0, int(self.resources.get('drones', 0)))
                # primary contribution from crews, small from drones
                increment = crews * self.params.get('rebuild_factor_per_crew', 2.0) + drones * 0.15
                # random factor
                increment *= (0.8 + random.random() * 0.4)
                self.rebuild_progress = min(100.0, self.rebuild_progress + increment)

                # Unblock some edges based on progress
                unblock_count = int(increment // 5)
                blocked_edges = [idx for idx, edge in enumerate(self.edges) if edge['blocked']]
                random.shuffle(blocked_edges)
                for idx in blocked_edges[:unblock_count]:
                    self.edges[idx]['blocked'] = False
                # Update roads_blocked
                self.roads_blocked = any(edge['blocked'] for edge in self.edges)

                # consume some crews gradually (simulating fatigue/rotation)
                consumed = min(self.resources.get('repair_crews', 0), max(0, int(increment // 3)))
                self.resources['repair_crews'] = max(0, self.resources.get('repair_crews', 0) - consumed)

                # when rebuild is complete, restore baseline and enter recovered cooldown
                if self.rebuild_progress >= self.params.get('rebuild_required', 100):
                    self.phase = 'recovered'
                    self.disaster = False
                    self.seismic_level = 0.0
                    self.roads_blocked = False
                    self.victims = 0
                    # Unblock all edges
                    for edge in self.edges:
                        edge['blocked'] = False
                    self.affected_nodes = []
                    self.affected_edges = []
                    # Update statistics
                    self.stats["disasters_completed"] += 1
                    # restore original baseline resources
                    self.resources = dict(self.initial_resources)
                    for k in self.resources.keys():
                        self.resources[k] = max(0, int(self.resources[k] * (0.9 + random.random() * 0.2)))
                    # cooldown steps before next random disaster
                    self.cooldown_counter = random.randint(2, 6)

            # RECOVERED: wait cooldown then trigger a new random disaster automatically
            elif self.phase == 'recovered':
                if self.cooldown_counter > 0:
                    self.cooldown_counter -= 1
                else:
                    # start a new random disaster
                    new_scenario = random.choice(['earthquake', 'flood', 'wildfire'])
                    intensity = round(random.random() * 0.9 + 0.1, 2)
                    self.trigger_disaster(scenario=new_scenario, intensity=float(intensity))

            # enforce non-negative resources/victims
            self.victims = max(0, int(self.victims))
            for k in list(self.resources.keys()):
                self.resources[k] = max(0, int(self.resources[k]))

    def save_victims(self, count: int) -> int:
        """Record victims saved (thread-safe). Returns actual count saved."""
        with self._lock:
            actual_saved = min(count, self.victims)
            self.victims = max(0, self.victims - actual_saved)
            self.victims_saved += actual_saved
            return actual_saved

    def use_resource(self, resource_name: str, amount: int) -> int:
        """Use a resource (thread-safe). Returns actual amount used."""
        with self._lock:
            if resource_name not in self.resources:
                return 0
            actual_used = min(amount, self.resources[resource_name])
            self.resources[resource_name] -= actual_used
            self.resources_used[resource_name] = self.resources_used.get(resource_name, 0) + actual_used
            return actual_used

    def reset(self) -> None:
        """Reset the environment to initial state."""
        with self._lock:
            self.time_step = 0
            self.scenario = None
            self.disaster = False
            self.phase = 'idle'
            self.victims = 0
            self.victims_saved = 0
            self.seismic_level = 0.0
            self.aftershock = False
            self.roads_blocked = False
            self.rebuild_progress = 0.0
            self.cooldown_counter = 0

            # Reset resources to default
            self.resources = {
                "ambulances": 5,
                "drones": 3,
                "medical_kits": 40,
                "repair_crews": 2,
                "food_packs": 50,
            }
            self.initial_resources = dict(self.resources)
            self.resources_used = {k: 0 for k in self.resources}

            # Reset affected areas
            self.affected_nodes = []
            self.affected_edges = []

            # Unblock all edges
            for edge in self.edges:
                edge['blocked'] = False

            # Reset statistics
            self.stats = {
                "total_victims_initial": 0,
                "victims_saved": 0,
                "disasters_completed": 0,
                "total_time_steps": 0,
            }
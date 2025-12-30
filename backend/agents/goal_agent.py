"""Goal-Based Agent - Plans rescue operations with pathfinding."""
from typing import Dict, List, Any, Optional, Tuple
from collections import deque
import heapq
from backend.agents.agent_base import Agent


class GoalBasedAgent(Agent):
    """
    Goal-based agent that creates and executes rescue plans.
    Uses actual graph pathfinding for route planning.
    Active during 'response' phase.
    """

    def __init__(self):
        super().__init__("GoalAgent")
        self.current_plan = None
        self._cached_graph = None
        self._last_plan_step = -1

    def _build_adjacency_list(self, nodes: List[Dict], edges: List[Dict]) -> Dict[int, List[Tuple[int, float, bool]]]:
        """Build adjacency list from nodes and edges. Returns {node_id: [(neighbor_id, distance, blocked), ...]}"""
        adj = {node['id']: [] for node in nodes}
        for edge in edges:
            from_id, to_id = edge['from'], edge['to']
            distance = edge.get('distance', 1.0)
            blocked = edge.get('blocked', False)
            # Bidirectional edges
            adj[from_id].append((to_id, distance, blocked))
            adj[to_id].append((from_id, distance, blocked))
        return adj

    def _find_path_dijkstra(self, adj: Dict, start: int, end: int,
                           avoid_blocked: bool = True) -> Optional[List[int]]:
        """Find shortest path using Dijkstra's algorithm."""
        if start == end:
            return [start]

        # Priority queue: (distance, node, path)
        pq = [(0, start, [start])]
        visited = set()

        while pq:
            dist, node, path = heapq.heappop(pq)

            if node in visited:
                continue
            visited.add(node)

            if node == end:
                return path

            for neighbor, edge_dist, blocked in adj.get(node, []):
                if neighbor in visited:
                    continue
                if avoid_blocked and blocked:
                    continue
                heapq.heappush(pq, (dist + edge_dist, neighbor, path + [neighbor]))

        return None  # No path found

    def _find_critical_nodes(self, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify high-priority nodes needing rescue based on vulnerability and population."""
        nodes = obs.get("nodes", [])
        affected = set(obs.get("affected_nodes", []))
        scenario = obs.get("scenario", "earthquake")

        critical = []
        for node in nodes:
            if node['id'] not in affected:
                continue

            vulnerability = node.get('vulnerability', {}).get(scenario, 1.0)
            population = node.get('population', 0)

            # Calculate priority score (higher = more critical)
            priority_score = vulnerability * (population / 100000)  # Normalize population

            if node['type'] in ['residential', 'public_service']:
                priority_score *= 1.5  # Prioritize residential and public services

            critical.append({
                'id': node['id'],
                'name': node['name'],
                'type': node['type'],
                'priority_score': priority_score,
                'population': population
            })

        # Sort by priority (highest first)
        critical.sort(key=lambda x: x['priority_score'], reverse=True)
        return critical[:5]  # Top 5 critical nodes

    def _plan_rescue_routes(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        """Create rescue plan with actual routes."""
        nodes = obs.get("nodes", [])
        edges = obs.get("edges", [])

        # Build graph
        adj = self._build_adjacency_list(nodes, edges)

        # Find critical nodes
        critical_nodes = self._find_critical_nodes(obs)

        # Find command center (PDMA - node 26)
        command_center = 26

        # Calculate routes to critical nodes
        routes = []
        for target in critical_nodes:
            path = self._find_path_dijkstra(adj, command_center, target['id'], avoid_blocked=True)

            if path is None:
                # Try finding path ignoring blocked roads (emergency)
                path = self._find_path_dijkstra(adj, command_center, target['id'], avoid_blocked=False)
                route_status = "blocked_route"
            else:
                route_status = "clear"

            if path:
                # Convert path to named route
                path_names = [nodes[nid]['name'] for nid in path if nid < len(nodes)]
                routes.append({
                    'target_id': target['id'],
                    'target_name': target['name'],
                    'path': path,
                    'path_names': path_names,
                    'status': route_status,
                    'priority': target['priority_score']
                })

        return {
            'type': 'rescue_plan',
            'routes': routes,
            'critical_nodes': critical_nodes,
            'command_center': command_center,
            'total_targets': len(routes)
        }

    def decide(self, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create rescue plans based on current situation."""
        msgs = []
        phase = obs.get("phase", "idle")
        time_step = obs.get("time_step", 0)

        # Only operate during response phase
        if phase != "response":
            return msgs

        # Don't re-plan every step (plan every 3 steps)
        if time_step - self._last_plan_step < 3 and self.current_plan:
            return msgs

        victims = obs.get("victims", 0)
        roads_blocked = obs.get("roads_blocked", False)

        if victims <= 0:
            return msgs

        # Generate rescue plan with actual pathfinding
        plan = self._plan_rescue_routes(obs)
        self.current_plan = plan
        self._last_plan_step = time_step

        # Determine message based on road situation
        if roads_blocked:
            blocked_count = sum(1 for e in obs.get("edges", []) if e.get("blocked"))
            message = f"Roads blocked ({blocked_count} routes) → Using alternate paths for rescue"
            priority = 8
        else:
            message = f"Planning rescue operations for {len(plan['routes'])} critical zones"
            priority = 6

        payload = {
            "message": message,
            "time_step": time_step,
            "plan": plan,
            "victims_remaining": victims,
            "roads_blocked": roads_blocked
        }

        msgs.append({"type": "plan", "payload": payload, "priority": priority})
        return msgs
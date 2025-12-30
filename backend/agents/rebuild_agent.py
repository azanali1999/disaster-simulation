"""Rebuild Agent - Manages infrastructure repair after disaster response."""
from typing import Dict, List, Any
from backend.agents.agent_base import Agent


class RebuildAgent(Agent):
    """
    Agent responsible for coordinating rebuild operations.
    Active during 'rebuild' phase only.
    """

    # Configuration
    FOOD_COST_PER_CREW = 5      # Food packs needed to mobilize a crew
    MIN_CREWS_FOR_REBUILD = 2  # Minimum crews needed

    def __init__(self):
        super().__init__("RebuildAgent")
        self._last_status_step = -1

    def decide(self, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Decide on rebuild operations."""
        msgs = []
        phase = obs.get('phase', 'idle')
        time_step = obs.get('time_step', 0)

        # Only active during rebuild phase
        if phase != 'rebuild':
            return msgs

        resources = obs.get('resources', {})
        progress = obs.get('rebuild_progress', 0)
        crews = resources.get('repair_crews', 0)
        drones = resources.get('drones', 0)

        # Calculate estimated completion time
        if crews > 0:
            rebuild_factor = obs.get('params', {}).get('rebuild_factor_per_crew', 2.0)
            increment_per_step = crews * rebuild_factor + drones * 0.15
            remaining = max(0, 100 - progress)
            estimated_steps = int(remaining / max(0.1, increment_per_step))
        else:
            estimated_steps = -1  # Unknown

        # Status report (every step during rebuild)
        status_payload = {
            'rebuild_progress': round(progress, 2),
            'available_crews': crews,
            'available_drones': drones,
            'estimated_steps_remaining': estimated_steps,
            'time_step': time_step
        }
        msgs.append({
            'type': 'repair_status',
            'payload': status_payload,
            'priority': 6
        })

        # Request crew mobilization if low
        if crews < self.MIN_CREWS_FOR_REBUILD:
            needed = self.MIN_CREWS_FOR_REBUILD - crews
            msgs.append({
                'type': 'repair_request',
                'payload': {
                    'reason': 'insufficient_crews',
                    'current_crews': crews,
                    'needed': needed,
                    'time_step': time_step
                },
                'priority': 8
            })

        # Progress milestone messages
        milestones = [25, 50, 75, 90]
        for milestone in milestones:
            if progress >= milestone and progress < milestone + 5:
                msgs.append({
                    'type': 'milestone',
                    'payload': {
                        'message': f'Rebuild progress reached {milestone}%',
                        'progress': round(progress, 2),
                        'time_step': time_step
                    },
                    'priority': 4
                })
                break

        return msgs

    def act(self, env, bus) -> None:
        """Execute rebuild decisions."""
        obs = self.sense(env, bus)
        decisions = self.decide(obs) or []

        for d in decisions:
            dtype = d.get('type')
            payload = d.get('payload', {})
            prio = d.get('priority', 1)

            if dtype == 'repair_request':
                needed = int(payload.get('needed', 1))
                added = 0
                source = None

                # Try to recruit crews using food (hiring temporary workers)
                available_food = env.resources.get('food_packs', 0)
                max_from_food = available_food // self.FOOD_COST_PER_CREW

                if max_from_food > 0:
                    add = min(needed, max_from_food)
                    # Use thread-safe resource methods
                    food_used = env.use_resource('food_packs', add * self.FOOD_COST_PER_CREW)
                    if food_used > 0:
                        crews_added = food_used // self.FOOD_COST_PER_CREW
                        env.resources['repair_crews'] = env.resources.get('repair_crews', 0) + crews_added
                        bus.send(self.name, 'repair_alloc', {
                            'added_crews': crews_added,
                            'source': 'food_recruitment',
                            'food_used': food_used,
                            'time_step': payload.get('time_step')
                        }, prio)
                        continue

                # If no food, can't add more crews (don't convert ambulances - unrealistic)
                bus.send(self.name, 'repair_blocked', {
                    'reason': 'insufficient_food_for_recruitment',
                    'needed': needed,
                    'available_food': available_food,
                    'required_food': needed * self.FOOD_COST_PER_CREW,
                    'time_step': payload.get('time_step')
                }, max(1, prio - 2))

            elif dtype == 'milestone':
                # Just forward milestone messages
                bus.send(self.name, dtype, payload, prio)

            else:
                # Forward status messages as-is
                bus.send(self.name, dtype or 'info', payload, prio)
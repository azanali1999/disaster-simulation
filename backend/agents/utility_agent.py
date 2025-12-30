"""Utility Agent - Optimizes resource allocation based on utility calculations."""
from typing import Dict, List, Any
from backend.agents.agent_base import Agent


class UtilityAgent(Agent):
    """
    Utility-based agent that optimizes resource allocation.
    Calculates expected utility of different allocation strategies.
    Active during 'response' phase only.
    """

    # Resource effectiveness parameters (victims saved per unit per step)
    # Higher values for faster, more visible progress
    AMBULANCE_CAPACITY = 500   # Victims per ambulance per step (each ambulance represents a fleet)
    DRONE_CAPACITY = 200       # Victims per drone per step (reconnaissance + rescue assist)
    MEDICAL_KIT_CAPACITY = 50  # Victims per kit per step (each kit represents a batch)
    FOOD_PACK_CAPACITY = 30    # Victims stabilized per step (each pack represents a batch)

    def __init__(self):
        super().__init__("UtilityAgent")
        self._last_alloc_step = -1
        self._deployed_resources = {}  # Track currently deployed resources

    def _calculate_utility(self, alloc: Dict[str, int], victims: int,
                           resources: Dict[str, int]) -> Dict[str, Any]:
        """
        Calculate the utility of a given allocation.
        Returns utility score and breakdown.
        """
        # Calculate victims helped by each resource type
        amb_helped = min(alloc.get("ambulances", 0) * self.AMBULANCE_CAPACITY, victims)
        remaining = max(0, victims - amb_helped)

        drone_helped = min(alloc.get("drones", 0) * self.DRONE_CAPACITY, remaining)
        remaining = max(0, remaining - drone_helped)

        kit_helped = min(alloc.get("medical_kits", 0) * self.MEDICAL_KIT_CAPACITY, remaining)
        remaining = max(0, remaining - kit_helped)

        food_helped = min(alloc.get("food_packs", 0) * self.FOOD_PACK_CAPACITY, remaining)
        remaining = max(0, remaining - food_helped)

        total_helped = amb_helped + drone_helped + kit_helped + food_helped

        # Utility = victims helped - resource cost (normalized)
        # We want to maximize helped victims while being resource-efficient
        resource_cost = (
            alloc.get("ambulances", 0) * 5 +  # Ambulances are expensive
            alloc.get("drones", 0) * 2 +
            alloc.get("medical_kits", 0) * 1 +
            alloc.get("food_packs", 0) * 0.5
        )

        utility_score = total_helped * 10 - resource_cost

        return {
            "utility_score": utility_score,
            "total_helped": total_helped,
            "remaining_victims": remaining,
            "breakdown": {
                "ambulances": amb_helped,
                "drones": drone_helped,
                "medical_kits": kit_helped,
                "food_packs": food_helped
            }
        }

    def _optimal_allocation(self, resources: Dict[str, int], victims: int) -> Dict[str, int]:
        """
        Calculate optimal resource allocation using utility maximization.
        Uses greedy approach with utility-based prioritization.
        """
        alloc = {"ambulances": 0, "drones": 0, "medical_kits": 0, "food_packs": 0}
        remaining_victims = victims

        # Priority order based on efficiency (victims helped per resource unit)
        # Ambulances: 15 victims, Drones: 5 victims, Kits: 3 victims, Food: 2 victims

        # Allocate ambulances first (most efficient)
        available_amb = resources.get("ambulances", 0)
        needed_amb = min(available_amb, (remaining_victims + self.AMBULANCE_CAPACITY - 1) // self.AMBULANCE_CAPACITY)
        alloc["ambulances"] = needed_amb
        remaining_victims = max(0, remaining_victims - needed_amb * self.AMBULANCE_CAPACITY)

        # Allocate drones
        if remaining_victims > 0:
            available_drones = resources.get("drones", 0)
            needed_drones = min(available_drones, (remaining_victims + self.DRONE_CAPACITY - 1) // self.DRONE_CAPACITY)
            alloc["drones"] = needed_drones
            remaining_victims = max(0, remaining_victims - needed_drones * self.DRONE_CAPACITY)

        # Allocate medical kits
        if remaining_victims > 0:
            available_kits = resources.get("medical_kits", 0)
            needed_kits = min(available_kits, (remaining_victims + self.MEDICAL_KIT_CAPACITY - 1) // self.MEDICAL_KIT_CAPACITY)
            alloc["medical_kits"] = needed_kits
            remaining_victims = max(0, remaining_victims - needed_kits * self.MEDICAL_KIT_CAPACITY)

        # Allocate food packs for remaining
        if remaining_victims > 0:
            available_food = resources.get("food_packs", 0)
            needed_food = min(available_food, (remaining_victims + self.FOOD_PACK_CAPACITY - 1) // self.FOOD_PACK_CAPACITY)
            alloc["food_packs"] = needed_food

        return alloc

    def decide(self, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Decide on resource allocation for this step."""
        msgs = []
        phase = obs.get("phase", "idle")
        time_step = obs.get("time_step", 0)

        # Only operate during response phase
        if phase != "response":
            self._deployed_resources = {}  # Reset when not in response
            return msgs

        resources = obs.get("resources", {})
        victims = obs.get("victims", 0)

        if victims <= 0:
            return msgs

        # Calculate how many victims we can save this step based on available resources
        # Each resource type contributes to saving victims progressively
        ambulances = resources.get("ambulances", 0)
        drones = resources.get("drones", 0)
        medical_kits = resources.get("medical_kits", 0)
        food_packs = resources.get("food_packs", 0)

        # Calculate potential victims saved this step
        potential_saved = (
            ambulances * self.AMBULANCE_CAPACITY +
            drones * self.DRONE_CAPACITY +
            min(medical_kits, 5) * self.MEDICAL_KIT_CAPACITY +  # Use up to 5 kits per step
            min(food_packs, 3) * self.FOOD_PACK_CAPACITY   # Use up to 3 food packs per step
        )

        if potential_saved > 0:
            # Calculate resources to consume this step
            kits_to_use = min(medical_kits, 5, (victims + self.MEDICAL_KIT_CAPACITY - 1) // self.MEDICAL_KIT_CAPACITY)
            food_to_use = min(food_packs, 3, (victims + self.FOOD_PACK_CAPACITY - 1) // self.FOOD_PACK_CAPACITY)

            alloc = {
                "ambulances": 0,  # Don't consume ambulances (they're reusable)
                "drones": 0,      # Don't consume drones (they're reusable)
                "medical_kits": kits_to_use,
                "food_packs": food_to_use
            }

            payload = {
                "message": f"Rescue operations in progress: {min(potential_saved, victims)} victims being rescued",
                "allocation": alloc,
                "expected_victims_helped": min(potential_saved, victims),
                "remaining_victims": max(0, victims - potential_saved),
                "active_resources": {
                    "ambulances": ambulances,
                    "drones": drones,
                    "medical_kits": medical_kits,
                    "food_packs": food_packs
                },
                "time_step": time_step
            }
            msgs.append({"type": "rescue", "payload": payload, "priority": 5})
        else:
            payload = {
                "message": "No resources available for rescue operations",
                "victims_remaining": victims,
                "time_step": time_step
            }
            msgs.append({"type": "status", "payload": payload, "priority": 1})

        return msgs

    def act(self, env, bus) -> None:
        """Execute rescue operations and save victims progressively."""
        obs = self.sense(env, bus)
        decisions = self.decide(obs) or []

        for d in decisions:
            payload = d.get("payload", {})

            if d.get("type") == "rescue":
                alloc = payload.get("allocation", {})
                active = payload.get("active_resources", {})

                # Consume expendable resources
                for resource_name, amount in alloc.items():
                    if amount > 0:
                        env.use_resource(resource_name, amount)

                # Calculate victims saved this step based on active (not consumed) resources
                victims_this_step = (
                    active.get("ambulances", 0) * self.AMBULANCE_CAPACITY +
                    active.get("drones", 0) * self.DRONE_CAPACITY +
                    alloc.get("medical_kits", 0) * self.MEDICAL_KIT_CAPACITY +
                    alloc.get("food_packs", 0) * self.FOOD_PACK_CAPACITY
                )

                if victims_this_step > 0:
                    actual_saved = env.save_victims(victims_this_step)
                    payload["actual_victims_saved"] = actual_saved
                    payload["message"] = f"Rescued {actual_saved} victims this step"

            # Send message to bus
            bus.send(self.name, d.get("type", "info"), payload, d.get("priority", 1))
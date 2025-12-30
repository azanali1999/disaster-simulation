# Rescue Agents - Disaster Response Simulation

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Core Components](#core-components)
    - [Environment](#environment)
    - [Message Bus](#message-bus)
    - [Orchestrator](#orchestrator)
5. [Agent System](#agent-system)
    - [Agent Base Class](#agent-base-class)
    - [Reflex Agent](#reflex-agent)
    - [Drone Recon Agent](#drone-recon-agent)
    - [Goal-Based Agent](#goal-based-agent)
    - [Utility Agent](#utility-agent)
    - [Rebuild Agent](#rebuild-agent)
6. [API Reference](#api-reference)
7. [Frontend Visualization](#frontend-visualization)
8. [Simulation Flow](#simulation-flow)
9. [Testing](#testing)
10. [Getting Started](#getting-started)

---

## Overview

**Rescue Agents** is a multi-agent disaster response simulation system designed to model emergency response scenarios in Karachi, Pakistan. The simulation uses various AI agent types to coordinate disaster relief efforts, including victim rescue, resource allocation, reconnaissance, and infrastructure rebuilding.

### Key Features

-   **Multi-Agent Architecture**: Five specialized agents working in coordination
-   **Real-time Simulation**: WebSocket support for live updates
-   **Geographic Modeling**: 27 nodes representing key Karachi locations with road network
-   **Multiple Disaster Types**: Earthquake, flood, and wildfire scenarios
-   **Resource Management**: Dynamic allocation of ambulances, drones, medical kits, repair crews, and food packs
-   **Phase-based Progression**: Idle → Response → Rebuild → Recovered cycle

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend                                │
│                    (visualizer.html)                            │
│    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│    │   Map View  │  │  Controls   │  │  Messages   │            │
│    │  (Leaflet)  │  │   Panel     │  │   Panel     │            │
│    └─────────────┘  └─────────────┘  └─────────────┘            │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/WebSocket
┌────────────────────────────┴────────────────────────────────────┐
│                      FastAPI Backend                            │
│                        (main.py)                                │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Environment │  │ Message Bus │  │ Orchestrator│              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                     │
│         └────────────────┼────────────────┘                     │
│                          │                                      │
│  ┌───────────────────────┴───────────────────────────┐          │
│  │                   Agents Layer                    │          │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐           │          │
│  │  │  Reflex  │ │  Drone   │ │   Goal   │           │          │
│  │  │  Agent   │ │  Recon   │ │  Agent   │           │          │
│  │  └──────────┘ └──────────┘ └──────────┘           │          │
│  │  ┌──────────┐ ┌──────────┐                        │          │
│  │  │ Utility  │ │ Rebuild  │                        │          │
│  │  │  Agent   │ │  Agent   │                        │          │
│  │  └──────────┘ └──────────┘                        │          │
│  └───────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
rescue-agents/
├── __init__.py                 # Package initialization
├── requirements.txt            # Dependencies (fastapi, uvicorn)
├── DOCUMENTATION.md            # This file
│
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application & API endpoints
│   ├── environment.py          # Disaster simulation environment
│   ├── message_bus.py          # Inter-agent communication system
│   ├── orchestrator.py         # Agent coordination & cycle management
│   │
│   └── agents/
│       ├── __init__.py
│       ├── agent_base.py       # Abstract base class for agents
│       ├── reflex_agent.py     # Immediate reactive responses
│       ├── drone_recon_agent.py# Reconnaissance operations
│       ├── goal_agent.py       # Goal-based planning with pathfinding
│       ├── utility_agent.py    # Resource allocation optimization
│       └── rebuild_agent.py    # Infrastructure repair coordination
│
├── frontend/
│   └── visualizer.html         # Web-based visualization interface
│
└── tests/
    └── test_simulation.py      # Comprehensive test suite
```

---

## Core Components

### Environment

**File**: `backend/environment.py`

The `Environment` class represents the disaster simulation world. It is thread-safe and manages:

#### State Variables

| Variable           | Type  | Description                                               |
| ------------------ | ----- | --------------------------------------------------------- |
| `phase`            | str   | Current phase: `idle`, `response`, `rebuild`, `recovered` |
| `scenario`         | str   | Disaster type: `earthquake`, `flood`, `wildfire`          |
| `victims`          | int   | Current number of victims needing rescue                  |
| `victims_saved`    | int   | Total victims rescued                                     |
| `seismic_level`    | float | Disaster intensity (0.0 - 1.0)                            |
| `aftershock`       | bool  | Whether an aftershock is occurring                        |
| `roads_blocked`    | bool  | Whether roads are blocked                                 |
| `rebuild_progress` | float | Rebuild completion percentage (0-100)                     |

#### Resources

```python
resources = {
    "ambulances": 5,      # Reusable rescue vehicles
    "drones": 3,          # Reconnaissance & support
    "medical_kits": 40,   # Consumable supplies
    "repair_crews": 2,    # Infrastructure repair teams
    "food_packs": 50,     # Emergency food supplies
}
```

#### Karachi Map Model

The environment includes a detailed graph of Karachi with **27 nodes** representing:

-   **District Centers** (7): Karachi Central, East, West, South, Malir, Korangi, Kemari
-   **Residential Areas** (6): Saddar, Lyari, Clifton, Gulshan-e-Iqbal, Orangi Town, North Nazimabad
-   **Commercial Areas** (5): Saddar Market, Burns Road, Tariq Road, Gulshan Commercial, Korangi Industrial
-   **Landmarks** (2): Jinnah International Airport, Port of Karachi
-   **Public Services** (7): Hospitals (JPMC, Civil, Aga Khan), Fire Stations, PDMA

Each node has:

-   Geographic coordinates (lat, lng)
-   Population
-   Infrastructure level
-   Vulnerability factors per disaster type

**Edges** connect nodes via roads and highways with:

-   Distance (km)
-   Type (road/highway)
-   Blocked status

#### Key Methods

```python
def trigger_disaster(scenario, intensity, resources=None)
    # Start a new disaster with specified parameters

def get_observation() -> Dict[str, Any]
    # Thread-safe snapshot of environment state

def update()
    # Advance simulation by one time step

def save_victims(count) -> int
    # Record victims saved, returns actual count

def use_resource(resource_name, amount) -> int
    # Consume resources, returns actual amount used

def reset()
    # Reset to initial idle state
```

---

### Message Bus

**File**: `backend/message_bus.py`

A thread-safe publish-subscribe messaging system for inter-agent communication.

#### Features

-   **Message History**: Configurable history retention (default 500 messages)
-   **Consumer Tracking**: Multiple consumers can independently track read positions
-   **Priority Support**: Messages can have priority levels

#### Message Structure

```python
{
    "id": 123,              # Unique message ID
    "type": "alert",        # Message type (alert, plan, alloc, recon, etc.)
    "sender": "ReflexAgent", # Sending agent name
    "payload": {...},       # Message-specific data
    "priority": 10,         # Priority level (higher = more important)
    "ts": 1704067200.0      # Unix timestamp
}
```

#### Key Methods

```python
def send(sender, msg_type, payload, priority=1, ts=None) -> int
    # Send a message, returns message ID

def read_all(consumer_id="default", clear=False) -> List[Dict]
    # Read new messages for a specific consumer

def read_recent(count=50) -> List[Dict]
    # Get most recent N messages without affecting state

def clear_old_messages(keep_recent=100)
    # Cleanup old messages from active queue
```

---

### Orchestrator

**File**: `backend/orchestrator.py`

Coordinates the execution of all agents through the sense-decide-act cycle.

#### Agent Priority Order

1. **ReflexAgent** - Immediate emergency alerts
2. **DroneReconAgent** - Area reconnaissance
3. **GoalBasedAgent** - Rescue route planning
4. **UtilityAgent** - Resource allocation
5. **RebuildAgent** - Infrastructure repair

#### Rescue Unit Management

The orchestrator spawns and manages animated rescue units:

| Unit Type    | Description                | Spawn Rate     |
| ------------ | -------------------------- | -------------- |
| Ambulance    | Medical rescue             | Every 2 cycles |
| Drone        | Reconnaissance             | Every 3 cycles |
| Medical Team | On-site treatment          | Every 4 cycles |
| Repair Crew  | Road/infrastructure repair | Every 3 cycles |

Units move through states: `dispatched` → `responding` → `returning`

#### Key Methods

```python
def run_cycle() -> Dict[str, Any]
    # Execute one simulation cycle for all agents

def pause() / resume()
    # Control simulation execution

def reset()
    # Reset orchestrator and all agents

def get_agent_positions() -> List[Dict]
    # Get current positions for visualization
```

---

## Agent System

All agents inherit from the abstract `Agent` base class and implement the **Sense-Decide-Act** cycle.

### Agent Base Class

**File**: `backend/agents/agent_base.py`

```python
class Agent(ABC):
    def sense(self, env, bus) -> Dict[str, Any]
        # Gather observations from environment and message bus

    @abstractmethod
    def decide(self, observation) -> List[Dict[str, Any]]
        # Make decisions based on observations (must implement)

    def act(self, env, bus)
        # Execute sense-decide-act cycle
```

---

### Reflex Agent

**File**: `backend/agents/reflex_agent.py`

**Purpose**: Immediate reactive responses to environmental conditions

**Active Phase**: Response only

**Behavior**:

-   Monitors seismic levels against threshold (default 0.5)
-   Generates emergency alerts based on severity
-   Detects and reports aftershocks

**Output Messages**:

```python
{
    "type": "alert",
    "payload": {
        "message": "ALERT: Seismic level 0.85 exceeds threshold...",
        "severity": "critical",  # critical, high, medium
        "seismic_level": 0.85,
        "aftershock": False,
        "affected_areas": 15
    },
    "priority": 10  # High priority for alerts
}
```

---

### Drone Recon Agent

**File**: `backend/agents/drone_recon_agent.py`

**Purpose**: Scout affected areas before rescue operations

**Active Phase**: Response only

**Parameters**:

-   `SCAN_RADIUS = 2` - Nodes scanned per drone per step
-   `VICTIMS_PER_SCAN = 3` - Victims identified per scan

**Behavior**:

-   Systematically scans all affected nodes
-   Tracks scanned vs unscanned areas
-   Reports reconnaissance progress and completion

**Output Messages**:

```python
{
    "type": "recon",
    "payload": {
        "message": "Drones scanning 6 areas...",
        "nodes_scanned": [1, 3, 5, 7, 9, 11],
        "drones_active": 3,
        "remaining_areas": 10
    }
}
```

---

### Goal-Based Agent

**File**: `backend/agents/goal_agent.py`

**Purpose**: Plan rescue operations with intelligent pathfinding

**Active Phase**: Response only

**Features**:

-   Uses **Dijkstra's algorithm** for shortest path calculation
-   Builds adjacency list from map graph
-   Identifies critical nodes based on vulnerability and population
-   Plans routes from PDMA (command center) to affected areas

**Priority Scoring**:

```
priority_score = vulnerability × (population / 100000)
// Residential and public service nodes get 1.5x multiplier
```

**Output Messages**:

```python
{
    "type": "plan",
    "payload": {
        "type": "rescue_plan",
        "routes": [
            {
                "target_name": "Orangi Town Residential",
                "path_names": ["PDMA", "Karachi Central", "Orangi Town"],
                "status": "clear",
                "priority": 15.6
            }
        ],
        "total_targets": 5
    }
}
```

---

### Utility Agent

**File**: `backend/agents/utility_agent.py`

**Purpose**: Optimize resource allocation using utility calculations

**Active Phase**: Response only

**Resource Effectiveness** (victims saved per unit per step):
| Resource | Capacity |
|----------|----------|
| Ambulance | 500 |
| Drone | 200 |
| Medical Kit | 50 |
| Food Pack | 30 |

**Utility Calculation**:

```python
utility_score = (total_victims_helped × 10) - resource_cost

resource_cost = (ambulances × 5) + (drones × 2) + (kits × 1) + (food × 0.5)
```

**Allocation Strategy**:

1. Allocate ambulances first (most efficient)
2. Use drones for remaining
3. Deploy medical kits (up to 5/step)
4. Use food packs for stabilization (up to 3/step)

**Output Messages**:

```python
{
    "type": "alloc",
    "payload": {
        "allocated": {"medical_kits": 5, "food_packs": 3},
        "victims_targeted": 400,
        "utility_score": 3850.5
    }
}
```

---

### Rebuild Agent

**File**: `backend/agents/rebuild_agent.py`

**Purpose**: Coordinate infrastructure repair after rescue phase

**Active Phase**: Rebuild only

**Parameters**:

-   `FOOD_COST_PER_CREW = 5` - Food packs to recruit one crew
-   `MIN_CREWS_FOR_REBUILD = 2` - Minimum crews needed

**Behavior**:

-   Reports rebuild progress and estimated completion
-   Requests crew mobilization if understaffed
-   Announces milestone achievements (25%, 50%, 75%, 90%)
-   Uses food packs to recruit temporary workers

**Output Messages**:

```python
{
    "type": "repair_status",
    "payload": {
        "rebuild_progress": 45.5,
        "available_crews": 3,
        "estimated_steps_remaining": 12
    }
}
```

---

## API Reference

**Base URL**: `http://localhost:8000`

### Endpoints

| Method | Endpoint     | Description                       |
| ------ | ------------ | --------------------------------- |
| GET    | `/`          | API info and available endpoints  |
| POST   | `/start`     | Start a new disaster simulation   |
| GET    | `/step`      | Execute one simulation step       |
| POST   | `/reset`     | Reset simulation to initial state |
| POST   | `/pause`     | Toggle pause/resume               |
| GET    | `/status`    | Get current simulation status     |
| GET    | `/grid`      | Get map grid data                 |
| GET    | `/agents`    | Get agent positions               |
| GET    | `/messages`  | Get recent messages               |
| GET    | `/stats`     | Get simulation statistics         |
| GET    | `/visualize` | Get text representation of grid   |
| WS     | `/ws`        | WebSocket for real-time updates   |

### Start Disaster Request

```json
POST /start
{
    "scenario": "earthquake",  // earthquake, flood, wildfire
    "intensity": 0.8,          // 0.1 - 1.0
    "resources": {             // Optional custom resources
        "ambulances": 10,
        "drones": 5
    }
}
```

### WebSocket Data Format

```json
{
    "type": "update",
    "environment": {
        "phase": "response",
        "victims": 1500,
        "seismic_level": 0.65,
        "resources": {...}
    },
    "messages": [...],
    "agents": [...],
    "orchestrator": {
        "cycle_count": 15,
        "paused": false
    }
}
```

---

## Frontend Visualization

**File**: `frontend/visualizer.html`

A comprehensive web-based interface built with:

-   **Leaflet.js** for interactive mapping
-   **Font Awesome** for icons
-   **WebSocket** for real-time updates

### Features

1. **Interactive Map**

    - Displays all Karachi nodes with appropriate markers
    - Shows road network with blocked/clear status
    - Animated rescue unit movements
    - Affected area highlighting

2. **Control Panel**

    - Scenario selection (earthquake, flood, wildfire)
    - Intensity slider (0.1 - 1.0)
    - Start/Stop/Reset/Pause buttons
    - Auto-step toggle

3. **Status Dashboard**

    - Current phase indicator
    - Victim count (initial, saved, remaining)
    - Resource levels with low warnings
    - Rebuild progress bar

4. **Message Feed**

    - Real-time agent communications
    - Color-coded by message type
    - Severity indicators

5. **Statistics Panel**
    - Save rate percentage
    - Resource usage breakdown
    - Timing metrics

---

## Simulation Flow

```
┌─────────┐     trigger_disaster()      ┌──────────┐
│  IDLE   │ ──────────────────────────► │ RESPONSE │
└─────────┘                             └────┬─────┘
     ▲                                       │
     │                           victims = 0 │
     │                         no aftershock │
     │                                       ▼
┌────┴─────┐    rebuild_progress ≥ 100   ┌───────────┐
│RECOVERED │ ◄────────────────────────── │  REBUILD  │
└──────────┘                             └───────────┘
     │
     │ cooldown = 0
     │ (auto-triggers new disaster)
     ▼
   [loop]
```

### Phase Details

#### Response Phase

-   Agents active: Reflex, Drone Recon, Goal, Utility
-   Seismic level naturally decays over time
-   Aftershocks can occur, adding new victims
-   Ends when: `victims = 0` AND `no aftershock`

#### Rebuild Phase

-   Agents active: Rebuild
-   Progress increments based on: `crews × 2.0 + drones × 0.15`
-   Roads gradually unblocked
-   Crews consumed over time (fatigue simulation)
-   Ends when: `rebuild_progress ≥ 100`

#### Recovered Phase

-   All resources restored
-   Cooldown period (2-6 steps)
-   Automatically triggers new random disaster

---

## Testing

**File**: `tests/test_simulation.py`

The test suite covers:

### Environment Tests

-   Initial state validation
-   Disaster trigger verification
-   Resource management
-   Victim saving mechanics
-   Reset functionality

### Message Bus Tests

-   Send and read operations
-   Consumer tracking
-   Message history
-   Reset behavior

### Agent Tests

-   Phase-specific operation
-   Resource allocation logic
-   Decision generation

### Running Tests

```bash
# Install pytest if needed
pip install pytest

# Run all tests
pytest tests/test_simulation.py -v

# Run specific test class
pytest tests/test_simulation.py::TestEnvironment -v
```

---

## Getting Started

### Prerequisites

-   Python 3.8+
-   pip

### Installation

```bash
# Navigate to project directory
cd rescue-agents

# Install dependencies
pip install -r requirements.txt
```

### Running the Backend

```bash
# Start the FastAPI server
uvicorn backend.main:app --reload
```

### Running the Frontend

1. Open `frontend/visualizer.html` in a web browser
2. Or serve it via a simple HTTP server:

```bash
cd frontend
python -m http.server 3000
```

Then open `http://localhost:3000/visualizer.html`

### Quick Test

1. Start the backend server
2. Open the frontend
3. Select a scenario (e.g., "Earthquake")
4. Set intensity (e.g., 0.8)
5. Click "Start Disaster"
6. Enable "Auto Step" to watch the simulation

---

## Configuration Parameters

### Environment Parameters (`params`)

| Parameter                 | Default | Description                         |
| ------------------------- | ------- | ----------------------------------- |
| `seismic_threshold`       | 0.5     | Alert threshold for seismic level   |
| `aftershock_factor`       | 0.3     | Base probability of aftershocks     |
| `road_block_chance`       | 0.4     | Base road blockage probability      |
| `rebuild_required`        | 100     | Progress needed to complete rebuild |
| `rebuild_factor_per_crew` | 2.0     | Progress per crew per step          |

### Resource Ranges by Scenario

| Scenario   | Ambulances | Drones | Medical Kits | Repair Crews | Food Packs |
| ---------- | ---------- | ------ | ------------ | ------------ | ---------- |
| Earthquake | 3-8        | 1-4    | 20-80        | 1-4          | 30-100     |
| Flood      | 2-6        | 2-6    | 15-60        | 2-6          | 40-120     |
| Wildfire   | 1-4        | 3-8    | 10-40        | 3-8          | 20-80      |

---

## License

This project was created for educational purposes as part of the MSAI Agentic AI course.

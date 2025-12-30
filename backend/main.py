"""
Rescue Agents Disaster Simulation API
FastAPI backend for multi-agent disaster response simulation
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List, Any
import asyncio
import logging
from starlette.concurrency import run_in_threadpool

from backend.environment import Environment
from backend.message_bus import MessageBus
from backend.orchestrator import Orchestrator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Rescue Agents Disaster Simulation",
    description="Multi-agent disaster response simulation for Karachi, Pakistan",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

# Global state (thread-safe components)
env = Environment()
bus = MessageBus()
orch = Orchestrator(env, bus)

# Track connected WebSocket clients
connected_clients: List[WebSocket] = []


# Request/Response Models
class StartRequest(BaseModel):
    """Request model for starting a disaster simulation."""
    scenario: str = Field(default="earthquake", description="Type of disaster")
    intensity: float = Field(default=0.8, ge=0.1, le=1.0, description="Disaster intensity (0.1-1.0)")
    resources: Optional[Dict[str, int]] = Field(default=None, description="Optional custom resource allocation")

    @validator('scenario')
    def validate_scenario(cls, v):
        valid_scenarios = ['earthquake', 'flood', 'wildfire']
        if v not in valid_scenarios:
            raise ValueError(f'Scenario must be one of: {valid_scenarios}')
        return v


class StatusResponse(BaseModel):
    """Response model for status endpoints."""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": str(exc)}
    )


# API Endpoints
@app.get("/", tags=["Info"])
def root():
    """API root - returns basic info."""
    return {
        "name": "Rescue Agents Disaster Simulation API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "start": "POST /start - Start a disaster simulation",
            "step": "GET /step - Run one simulation step",
            "reset": "POST /reset - Reset the simulation",
            "pause": "POST /pause - Pause/Resume simulation",
            "status": "GET /status - Get current status",
            "grid": "GET /grid - Get map grid data",
            "agents": "GET /agents - Get agent positions",
            "messages": "GET /messages - Get recent messages",
            "stats": "GET /stats - Get simulation statistics",
            "ws": "WS /ws - WebSocket for real-time updates"
        }
    }


@app.post("/start", tags=["Simulation"])
def start_disaster(payload: StartRequest):
    """Start a new disaster simulation."""
    try:
        # Reset before starting new disaster
        if env.phase != 'idle':
            orch.reset()

        env.trigger_disaster(
            scenario=payload.scenario,
            intensity=payload.intensity,
            resources=payload.resources
        )

        obs = env.get_observation()

        logger.info(f"Started disaster: {payload.scenario} at intensity {payload.intensity}")

        return {
            "status": "success",
            "message": f"Disaster '{payload.scenario}' triggered successfully",
            "scenario": payload.scenario,
            "intensity": payload.intensity,
            "initial_victims": obs.get("victims"),
            "affected_areas": len(obs.get("affected_nodes", [])),
            "resources": obs.get("resources")
        }
    except Exception as e:
        logger.error(f"Error starting disaster: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/step", tags=["Simulation"])
def step():
    """Execute one simulation step."""
    try:
        # Check if simulation is active
        if env.phase == 'idle':
            return {
                "status": "idle",
                "message": "No active disaster. Use POST /start to begin.",
                "environment": env.get_observation(),
                "messages": []
            }

        result = orch.run_cycle()

        # Get messages for this step (using HTTP consumer)
        messages = bus.read_all(consumer_id="http_step")

        # Get agent positions for visualization
        agent_positions = orch.get_agent_positions()

        return {
            "status": "success",
            "cycle": result.get("cycle"),
            "environment": env.get_observation(),
            "messages": messages,
            "agents": agent_positions
        }
    except Exception as e:
        logger.error(f"Error in step: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset", tags=["Simulation"])
def reset_simulation():
    """Reset the simulation to initial state."""
    try:
        orch.reset()
        logger.info("Simulation reset")

        return {
            "status": "success",
            "message": "Simulation reset to initial state",
            "environment": env.get_observation()
        }
    except Exception as e:
        logger.error(f"Error resetting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pause", tags=["Simulation"])
def toggle_pause():
    """Toggle pause state of the simulation."""
    try:
        if orch.is_paused():
            orch.resume()
            status = "resumed"
        else:
            orch.pause()
            status = "paused"

        return {
            "status": "success",
            "simulation_state": status,
            "message": f"Simulation {status}"
        }
    except Exception as e:
        logger.error(f"Error toggling pause: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status", tags=["Simulation"])
def get_status():
    """Get current simulation status."""
    try:
        obs = env.get_observation()
        orch_status = orch.get_status()

        return {
            "status": "success",
            "simulation": {
                "phase": obs.get("phase"),
                "time_step": obs.get("time_step"),
                "scenario": obs.get("scenario"),
                "disaster_active": obs.get("disaster"),
                "paused": orch_status.get("paused"),
                "cycle_count": orch_status.get("cycle_count")
            },
            "victims": {
                "current": obs.get("victims"),
                "saved": obs.get("victims_saved"),
                "initial": obs.get("stats", {}).get("total_victims_initial", 0)
            },
            "resources": obs.get("resources"),
            "conditions": {
                "seismic_level": obs.get("seismic_level"),
                "aftershock": obs.get("aftershock"),
                "roads_blocked": obs.get("roads_blocked"),
                "rebuild_progress": obs.get("rebuild_progress")
            }
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/grid", tags=["Map"])
def get_grid():
    """Get map grid data for visualization."""
    try:
        obs = env.get_observation()
        return {
            "status": "success",
            "nodes": obs.get("nodes", []),
            "edges": obs.get("edges", []),
            "affected_nodes": obs.get("affected_nodes", []),
            "affected_edges": obs.get("affected_edges", [])
        }
    except Exception as e:
        logger.error(f"Error getting grid: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents", tags=["Agents"])
def get_agents():
    """Get current agent positions and status for visualization."""
    try:
        positions = orch.get_agent_positions()
        status = orch.get_status()

        return {
            "status": "success",
            "phase": env.phase,
            "agents": status.get("agents", []),
            "positions": positions
        }
    except Exception as e:
        logger.error(f"Error getting agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/messages", tags=["Messages"])
def get_messages(count: int = 50):
    """Get recent agent messages."""
    try:
        messages = bus.read_recent(count=count)
        return {
            "status": "success",
            "count": len(messages),
            "messages": messages
        }
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", tags=["Statistics"])
def get_statistics():
    """Get simulation statistics."""
    try:
        obs = env.get_observation()
        stats = obs.get("stats", {})

        # Calculate additional metrics
        initial_victims = stats.get("total_victims_initial", 0)
        saved = obs.get("victims_saved", 0)
        remaining = obs.get("victims", 0)

        save_rate = (saved / max(1, initial_victims)) * 100 if initial_victims > 0 else 0

        # Resource efficiency
        resources_used = obs.get("resources_used", {})
        initial_resources = obs.get("initial_resources", {})

        return {
            "status": "success",
            "victims": {
                "initial": initial_victims,
                "saved": saved,
                "remaining": remaining,
                "save_rate_percent": round(save_rate, 2)
            },
            "resources": {
                "initial": initial_resources,
                "remaining": obs.get("resources", {}),
                "used": resources_used
            },
            "timing": {
                "time_steps": obs.get("time_step", 0),
                "total_time_steps": stats.get("total_time_steps", 0),
                "disasters_completed": stats.get("disasters_completed", 0)
            },
            "current_state": {
                "phase": obs.get("phase"),
                "scenario": obs.get("scenario"),
                "rebuild_progress": obs.get("rebuild_progress", 0)
            }
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/visualize", tags=["Map"])
def visualize_grid():
    """Get text representation of the grid."""
    try:
        return {
            "status": "success",
            "grid_text": env.get_grid_text()
        }
    except Exception as e:
        logger.error(f"Error visualizing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time simulation updates."""
    await websocket.accept()
    connected_clients.append(websocket)
    consumer_id = f"ws_{id(websocket)}"

    logger.info(f"WebSocket client connected: {consumer_id}")

    try:
        while True:
            # Only run cycles if not paused and not idle
            if not orch.is_paused() and env.phase != 'idle':
                await run_in_threadpool(orch.run_cycle)

            # Get current state
            messages = bus.read_all(consumer_id=consumer_id)
            agent_positions = orch.get_agent_positions()

            data = {
                "type": "update",
                "environment": env.get_observation(),
                "messages": messages,
                "agents": agent_positions,
                "orchestrator": orch.get_status()
            }

            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                break

            # Throttle updates
            await asyncio.sleep(0.8)

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {consumer_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
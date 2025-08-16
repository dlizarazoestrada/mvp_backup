"""
Cortex API Mock Server (Band Power Version)

This script simulates the Emotiv Cortex API WebSocket, specifically for the
'pow' (band power) data stream. It is designed to be run as a separate process.
"""
import asyncio
import json
import random
import websockets
import numpy as np
from backend.log_config import logger

# --- Configuration ---
HOST = 'localhost'
PORT = 6868
MOCK_HEADSETS = [
    {"id": "EPOCX-MOCK-1234", "status": "connected", "customName": "Mock EPOC X 1"},
    {"id": "EPOCX-MOCK-5678", "status": "connected", "customName": "Mock EPOC X 2"},
    {"id": "EPOCX-MOCK-9101", "status": "available", "customName": "Mock EPOC X 3"},
    {"id": "INSIGHT-MOCK-1234", "status": "connected", "customName": "Mock Insight 1"},
    {"id": "INSIGHT-MOCK-5678", "status": "connected", "customName": "Mock Insight 2"},
    {"id": "INSIGHT-MOCK-9101", "status": "available", "customName": "Mock Insight 3"},
]
CHANNELS = ["AF3", "F7", "F3", "FC5", "T7", "P7", "O1", "O2", "P8", "T8", "FC6", "F4", "F8", "AF4"]
BANDS = ["theta", "alpha", "betaL", "betaH", "gamma"]
STREAM_INTERVAL = 0.125 # 8 Hz

# --- Helper Functions ---
def create_response(request_id, result):
    return json.dumps({"id": request_id, "jsonrpc": "2.0", "result": result})

def create_power_generator():
    """
    Creates a generator that yields simulated 'pow' data packets.
    The simulation is designed to produce a wide range of Alpha/Beta ratios
    that swing above and below the population baseline (~12.44) to allow
    for testing the full range of scores (0-100).
    """
    time_step = 0
    while True:
        # Simulate a "mental state" that slowly oscillates between stressed and relaxed
        # A value of -1 represents a "stressed" state (high beta), +1 a "relaxed" state (high alpha)
        mental_state = np.sin(time_step / 50) # Slower, wider oscillation

        power_data = []
        for _ in CHANNELS:
            # Base power levels
            theta = random.uniform(1, 3)
            gamma = random.uniform(0.5, 2)
            
            # Modulate Alpha and Beta based on the simulated mental state
            if mental_state > 0: # Relaxed state
                # High alpha, low beta
                alpha = mental_state * random.uniform(15, 30) + random.uniform(1, 3)
                betaL = (1 - mental_state) * random.uniform(5, 10) + random.uniform(1, 2)
                betaH = (1 - mental_state) * random.uniform(3, 8) + random.uniform(1, 2)
            else: # Stressed state
                # Low alpha, high beta
                alpha = abs(mental_state) * random.uniform(1, 5) + random.uniform(1, 3)
                betaL = abs(mental_state) * random.uniform(10, 20) + random.uniform(1, 2)
                betaH = abs(mental_state) * random.uniform(8, 15) + random.uniform(1, 2)

            power_data.extend([theta, alpha, betaL, betaH, gamma])
        
        yield json.dumps({"pow": power_data, "sid": "mock-session-id"})
        time_step += 1

# --- Main Server Logic ---
async def data_streamer(websocket, path):
    logger.info("[Mock Server] Starting 'pow' data stream...")
    power_generator = create_power_generator()
    try:
        while True:
            await asyncio.sleep(STREAM_INTERVAL)
            await websocket.send(next(power_generator))
    except websockets.exceptions.ConnectionClosed:
        logger.info("[Mock Server] Connection closed, stopping data stream.")
    except Exception as e:
        logger.error(f"[Mock Server] Error in data streamer: {e}")

async def handler(websocket, path=None):
    logger.info(f"[Mock Server] Client connected from {websocket.remote_address}")
    streaming_task = None
    try:
        async for message in websocket:
            request = json.loads(message)
            req_id = request.get('id', 1)
            method = request.get('method')
            logger.info(f"[Mock Server] Received method: {method}")

            if method == 'requestAccess':
                response = create_response(req_id, {"accessGranted": True})
            elif method == 'authorize':
                response = create_response(req_id, {"cortexToken": "mock-cortex-token"})
            elif method == 'queryHeadsets':
                response = create_response(req_id, MOCK_HEADSETS)
            elif method == 'controlDevice':
                response = create_response(req_id, {"command": "connect", "message": "Connection successful."})
            elif method == 'createSession':
                response = create_response(req_id, {"id": "mock-session-id", "status": "active"})
            elif method == 'subscribe':
                response = create_response(req_id, {"success": [{"streamName": "pow", "message": "Subscribed successfully"}]})
                if not streaming_task:
                    streaming_task = asyncio.create_task(data_streamer(websocket, path))
            else:
                logger.warning(f"[Mock Server] Received unknown method: {method}")
                response = json.dumps({"id": req_id, "error": {"code": -32601, "message": "Method not found"}})

            await websocket.send(response)
            logger.info(f"[Mock Server] Sent response for: {method}")

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"[Mock Server] Client disconnected from {websocket.remote_address}")
    except Exception as e:
        logger.error(f"[Mock Server] An error occurred: {e}", exc_info=True)
    finally:
        if streaming_task:
            streaming_task.cancel()
            logger.info("[Mock Server] Data streaming task cancelled.")

async def main():
    logger.info(f"--- Starting Mock Cortex API Server on ws://{HOST}:{PORT} ---")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()

def start_mock_server():
    """Starts the mock server. This function is intended to be called in a new process."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n--- Mock Cortex API Server shutting down ---")

if __name__ == "__main__":
    start_mock_server()

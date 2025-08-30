"""
This file sets up the Flask server.
It uses a time-window aggregation approach for accurate scoring.
This module is designed to be importable and started from a master script.
"""
import eventlet
# Crucial for 'eventlet' to work. It patches standard Python libraries to be non-blocking.
# This must be done BEFORE any other modules (like socketio or flask) are imported.
eventlet.monkey_patch()

from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO
from flask_cors import CORS
import threading
import os
import numpy as np
import time
import sys

# Local imports (using absolute imports from the project root)
from backend.model_interface import get_score_from_ratio
from backend.cortex_client import CortexClient
from backend import config 
from backend.log_config import logger
from backend import eeg_processor

# --- Path Setup ---
# When running inside PyInstaller, the executable's directory is sys._MEIPASS
# In development, it's the script's directory.
_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
# The 'frontend' folder is now a sibling to the 'backend_executable' inside 'resources'
frontend_folder = os.path.join(_dir, '..', 'frontend')

# Configure the Flask app
app = Flask(__name__, static_folder=frontend_folder, static_url_path='')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- App State Management ---
class AppState:
    def __init__(self):
        self.cortex_client = None
        self.session_timer = None
        self.processing_thread = None
        self.stop_processing = threading.Event()
        
        self.scores = []
        self.data_buffer = [] # Buffer for incoming 'pow' data packets
        self.buffer_lock = threading.Lock()
        self.is_recording = False

    def reset_connection(self):
        logger.info("Resetting entire application connection state...")
        self.stop_processing.set()
        if self.processing_thread and self.processing_thread.is_alive():
            logger.debug("Joining processing thread...")
            self.processing_thread.join()
        if self.session_timer:
            logger.debug("Cancelling session timer...")
            self.session_timer.cancel()
        if self.cortex_client:
            logger.debug("Disconnecting Cortex client...")
            self.cortex_client.disconnect()
        
        self.__init__() # Reset all state variables to default
        logger.info("Application state has been fully reset.")

    def reset_recording(self):
        logger.info("Resetting recording state...")
        self.stop_processing.set()
        if self.processing_thread and self.processing_thread.is_alive():
            logger.debug("Joining processing thread for recording reset...")
            self.processing_thread.join()
        if self.session_timer:
            logger.debug("Cancelling session timer for recording reset...")
            self.session_timer.cancel()

        with self.buffer_lock:
            logger.debug(f"Clearing data buffer ({len(self.data_buffer)} items).")
            self.data_buffer = []
        self.scores = []
        self.is_recording = False
        self.session_timer = None
        self.processing_thread = None
        self.stop_processing.clear()
        logger.info("Recording state has been reset.")

state = AppState()

def force_disconnect_and_notify():
    logger.warning("Forcing disconnection due to unexpected connection loss with Cortex.")
    socketio.emit('server_disconnected', {'message': 'Connection to device lost unexpectedly.'})
    state.reset_connection()

# --- Data Processing ---
def power_data_callback(data: dict):
    """Callback to receive 'pow' data and add it to a buffer."""
    if not state.is_recording:
        logger.debug("Received power data, but recording is not active. Discarding.")
        return

    with state.buffer_lock:
        state.data_buffer.append(data)
    logger.debug(f"Added power data to buffer. Buffer size: {len(state.data_buffer)}")

def process_data_window():
    """
    This function runs in a separate thread and processes the data buffer
    every second.
    """
    logger.info("Data processing thread started.")
    while not state.stop_processing.is_set():
        time.sleep(1) # Process data once per second
        
        with state.buffer_lock:
            if not state.data_buffer:
                continue # No data to process
            
            # Create a local copy and clear the buffer immediately
            local_buffer = state.data_buffer[:]
            state.data_buffer = []
        
        logger.debug(f"Processing window with {len(local_buffer)} data packets.")
        # Process the copied data without holding the lock
        ratios = [eeg_processor.process_band_power_data(data) for data in local_buffer]
        valid_ratios = [r for r in ratios if r is not None]

        if not valid_ratios:
            logger.warning("No valid alpha/beta ratios in the last second's data window.")
            continue
            
        # Calculate the average ratio for the window
        average_ratio = np.mean(valid_ratios)
        score = get_score_from_ratio(average_ratio)
        
        state.scores.append(score)
        socketio.emit('new_score', {'score': score})
        logger.info(f"Processed {len(local_buffer)} packets. Valid ratios: {len(valid_ratios)}. Avg Ratio: {average_ratio:.2f}. Score: {score}")
    logger.info("Data processing thread stopped.")

def end_recording_session():
    logger.info("Recording timer finished. Ending recording session.")
    avg_score = int(np.mean(state.scores)) if state.scores else 0
    logger.info(f"Calculated average score: {avg_score} from {len(state.scores)} scores.")
    socketio.emit('recording_ended', {'average_score': avg_score})
    state.reset_recording()

# --- API Endpoints ---
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/connect', methods=['POST'])
def connect_and_query_headsets():
    logger.info("Received request on /api/connect")
    state.reset_connection()
    try:
        # The CORTEX_URL is now correctly set at startup by start_app_server
        config.validate_credentials_for_real_connection(config.CORTEX_URL)
        client = CortexClient(config.CLIENT_ID, config.CLIENT_SECRET, config.CORTEX_URL)
        headsets = client.connect_and_authorize()
        state.cortex_client = client
        logger.info(f"Successfully connected and found {len(headsets)} headsets.")
        return {"status": "success", "headsets": headsets}
    except Exception as e:
        logger.error(f"Error on /api/connect: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500

@app.route('/api/headsets', methods=['GET'])
def get_headsets():
    logger.info("Received request on /api/headsets")
    if not state.cortex_client:
        logger.error("Attempted to query headsets before connection was initiated.")
        return {"status": "error", "message": "Connection not initiated."}, 400
    try:
        headsets = state.cortex_client.query_headsets()
        logger.info(f"Successfully re-queried and found {len(headsets)} headsets.")
        return {"status": "success", "headsets": headsets}
    except Exception as e:
        logger.error(f"Error on /api/headsets: {e}", exc_info=True)
        return {"status": "error", "message": "Failed to query headsets."}, 500

@app.route('/api/select_headset', methods=['POST'])
def select_headset():
    data = request.get_json()
    logger.info(f"Received request on /api/select_headset with data: {data}")
    headset_id = data.get('headsetId')
    if not headset_id or not state.cortex_client:
        logger.error(f"Invalid request on /api/select_headset. Headset ID: {headset_id}, Client Exists: {state.cortex_client is not None}")
        return {"status": "error", "message": "Missing headsetId or initial connection not made."}, 400

    try:
        state.cortex_client.set_disconnect_callback(force_disconnect_and_notify)
        state.cortex_client.connect_to_headset(headset_id)
        state.cortex_client.set_data_callback(power_data_callback)
        logger.info(f"Successfully connected to headset {headset_id}.")
        return {"status": "success", "message": "Device connected and ready."}
    except Exception as e:
        logger.error(f"Error on /api/select_headset for headset {headset_id}: {e}", exc_info=True)
        state.reset_connection()
        return {"status": "error", "message": str(e)}, 500

@app.route('/api/start_recording', methods=['POST'])
def start_recording():
    data = request.get_json()
    logger.info(f"Received request on /api/start_recording with data: {data}")
    duration = data.get('duration')
    if not state.cortex_client or not state.cortex_client.is_session_active():
        logger.error("Attempted to start recording without a connected device.")
        return {"status": "error", "message": "Device not connected."}, 400
    if state.is_recording:
        logger.warning("Attempted to start a recording while one is already in progress.")
        return {"status": "error", "message": "A recording is already in progress."}, 400

    state.reset_recording()
    state.is_recording = True
    
    # Start the processing thread
    logger.info("Starting data processing thread.")
    state.processing_thread = threading.Thread(target=process_data_window)
    state.processing_thread.start()
    
    # Start the session timer
    logger.info(f"Starting recording session timer for {duration} seconds.")
    state.session_timer = threading.Timer(duration, end_recording_session)
    state.session_timer.start()

    socketio.emit('recording_started', {'duration': duration})
    logger.info("Recording started successfully.")
    return {"status": "success"}

@app.route('/api/restart_recording', methods=['POST'])
def restart_recording():
    logger.info("Received request on /api/restart_recording")
    if state.is_recording:
        logger.info("A recording is active. Resetting recording state.")
        state.reset_recording()
        socketio.emit('recording_cancelled', {})
    else:
        logger.info("No active recording. Request will have no effect.")
    return {"status": "success", "message": "Recording session cancelled."}

@app.route('/api/disconnect', methods=['POST'])
def disconnect_device():
    logger.info("Received request on /api/disconnect. Tearing down connection.")
    state.reset_connection()
    return {"status": "success"}

# --- WebSocket Events ---
@socketio.on('connect')
def handle_socket_connect():
    logger.info(f'Frontend client connected with SID: {request.sid}')

@socketio.on('disconnect')
def handle_socket_disconnect():
    logger.warning(f'Frontend client disconnected with SID: {request.sid}. Resetting server state.')
    state.reset_connection()

# --- Server Start ---
def start_app_server(host='127.0.0.1', port=5000, use_mock=False):
    """
    Starts the Flask-SocketIO server and configures it for mock or real mode.
    """
    if use_mock:
        logger.info("Configuring application to use MOCK Cortex server.")
        config.CORTEX_URL = config.CORTEX_URL_MOCK
    else:
        logger.info("Configuring application to use REAL Cortex server.")
        config.CORTEX_URL = config.CORTEX_URL_REAL
    
    logger.info(f"--- Starting Main Application Server on http://{host}:{port} ---")
    # use_reloader=False is important to prevent the server from starting twice
    # allow_unsafe_werkzeug is not needed when using eventlet
    socketio.run(app, host=host, port=port, use_reloader=False)

if __name__ == '__main__':
    # This allows running the server directly for development
    # In direct execution, it will default to using the REAL server.
    start_app_server()

"""
Main entry point for the backend server.
This script will launch the Flask server which includes the WebSocket handling.
"""
import os
import sys

# Add the parent directory to Python path so 'backend' can be imported
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)
from scoring_server import app, socketio
from log_config import logger
import webbrowser
import threading

def open_browser():
    """
    Opens the default web browser to the frontend page.
    """
    logger.info("Opening browser to http://127.0.0.1:5000")
    webbrowser.open_new('http://127.0.0.1:5000')

if __name__ == '__main__':
    # We run the browser opening in a separate thread to not block the server start
    threading.Timer(1, open_browser).start()
    logger.info("Starting Flask server...")
    # Use the aiohttp-based server for WebSocket support
    socketio.run(app, host='127.0.0.1', port=5000)

"""
Main entry point for the backend server.
This script will launch the Flask server which includes the WebSocket handling.
"""
import os
import sys

# Monkey patch for socketio server
import eventlet
eventlet.monkey_patch()

from .scoring_server import app, socketio
from .log_config import logger


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting server on 127.0.0.1:{port}")
    socketio.run(app, host='127.0.0.1', port=port, debug=False)
    logger.info(f"Server started on 127.0.0.1:{port}")

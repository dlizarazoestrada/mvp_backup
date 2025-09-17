"""
Main entry point for the backend server.
This script will launch the Flask server which includes the WebSocket handling.
"""
import os
import sys

from .scoring_server import app, socketio
from .log_config import logger


if __name__ == '__main__':
    logger.info("Starting server on 127.0.0.1:5000")
    socketio.run(app, host='127.0.0.1', port=5000, debug=False)
    logger.info("Server started on 127.0.0.1:5000")

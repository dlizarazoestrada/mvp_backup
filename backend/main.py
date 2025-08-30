"""
Main entry point for the backend server.
This script will launch the Flask server which includes the WebSocket handling.
"""
import os
import sys
import threading
from urllib.request import pathname2url
import webbrowser

from .scoring_server import app, socketio
from .log_config import logger


def open_browser():
    # Construct the file URL for the local HTML file
    # Get the absolute path to the frontend index.html
    # This path needs to be correct both in development and when packaged
    if hasattr(sys, '_MEIPASS'):
        # In packaged app, frontend is a sibling directory
        base_path = os.path.join(sys._MEIPASS, '..', 'frontend')
    else:
        # In development, go up two levels from backend/ and then to frontend/
        base_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    
    file_path = os.path.abspath(os.path.join(base_path, 'index.html'))
    webbrowser.open(f'file:{pathname2url(file_path)}')


if __name__ == '__main__':
    if os.environ.get('OPEN_BROWSER', '0') == '1':
        # We run the browser opening in a separate thread to not block the server start
        threading.Timer(1, open_browser).start()
    
    logger.info("Starting server on 127.0.0.1:5000")
    socketio.run(app, host='127.0.0.1', port=5000, debug=False)

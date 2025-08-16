"""
Main entry point for the Mental Health Quality MVP application.

This script launches the main Flask application and, optionally, the mock
Cortex API server in separate threads. It also opens the user's web browser
to the application's URL.

Usage:
    - To run with the real Cortex API:
      python run.py

    - To run with the mock Cortex API for testing:
      python run.py --mock
"""
import threading
import time
import webbrowser
import argparse
import sys
import os

# The monkey-patching is now done inside scoring_server.py

# Add the project root directory to the Python path.
# This allows for absolute imports like 'from backend.module import ...'
# and is crucial for PyInstaller to correctly resolve modules.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.scoring_server import start_app_server
from backend.cortex_mock_server import start_mock_server
from backend.log_config import logger

# --- Configuration ---
HOST = "127.0.0.1"
PORT = 5000

def open_browser():
    """Waits a moment for the server to start, then opens the web browser."""
    try:
        # Increased delay slightly to ensure both servers have time to bind to ports
        time.sleep(3) 
        webbrowser.open(f"http://{HOST}:{PORT}")
        logger.info("Opened web browser at the application URL.")
    except Exception as e:
        logger.error(f"Could not open web browser: {e}")

if __name__ == "__main__":
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description="Run the Mental Health MVP Application.",
        formatter_class=argparse.RawTextHelpFormatter 
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        help="Run the application with the mock Cortex API server for development and testing."
    )
    args = parser.parse_args()

    logger.info("--- Application Starting ---")

    # --- Thread Management ---
    if args.mock:
        logger.info("Mock mode enabled. Starting mock Cortex API server in a background thread...")
        mock_thread = threading.Thread(target=start_mock_server)
        mock_thread.daemon = True  # Allows main thread to exit even if this thread is running
        mock_thread.start()

    # The main application server will run in the main thread.
    # We open the browser in a separate thread so it doesn't block the server startup.
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()

    try:
        # This will now block and run the Flask-SocketIO server directly
        logger.info("Starting main application server...")
        start_app_server(HOST, PORT, args.mock)
    except KeyboardInterrupt:
        logger.info("--- Keyboard interrupt detected. Shutting down. ---")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        logger.info("--- Application Shutdown Complete ---")

import os
from dotenv import load_dotenv

# Load environment variables from a .env file at the project root
# The path is constructed to be relative to this config.py file
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Emotiv Cortex API Credentials ---
# These are loaded from the environment variables.
# The user must create a .env file in the project root based on .env.example.
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# --- URL Configuration ---
# These are the default URLs. The main application can override CORTEX_URL at runtime.
CORTEX_URL_REAL = "wss://localhost:6868"
CORTEX_URL_MOCK = "ws://localhost:6868"

# Default to the real URL.
CORTEX_URL = CORTEX_URL_REAL

# --- Validation ---
# This check is now more direct. If the URL is the real one, credentials must exist.
def validate_credentials_for_real_connection(url):
    if url == CORTEX_URL_REAL and (not CLIENT_ID or not CLIENT_SECRET):
        raise ValueError("CLIENT_ID and CLIENT_SECRET must be set in your .env file to connect to the real Cortex API.")

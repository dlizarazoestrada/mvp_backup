"""
This file contains the full implementation for the Cortex API client.
It handles the entire connection, authorization, and subscription flow.
"""
import websocket
import json
import ssl
import threading
import time
from backend.log_config import logger

class CortexClient:
    def __init__(self, client_id, client_secret, url):
        self.url = url
        self.client_id = client_id
        self.client_secret = client_secret
        self.ws = None
        self.thread = None
        self.request_id_counter = 1
        self.responses = {}
        self.data_stream_callback = None
        self.on_disconnect_callback = None

        self.auth_token = None
        self.headset_id = None
        self.session_id = None

    def _send_request(self, method, params={}):
        if not self.ws or not self.ws.connected:
             raise ConnectionAbortedError("WebSocket is not connected.")
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self.request_id_counter
        }
        request_json = json.dumps(request)
        logger.debug(f"--> SEND: {request_json}")
        self.ws.send(request_json)
        request_id = self.request_id_counter
        self.request_id_counter += 1
        return request_id

    def _wait_for_response(self, request_id, timeout=15):
        start_time = time.time()
        while time.time() - start_time < timeout:
            if request_id in self.responses:
                response = self.responses.pop(request_id)
                logger.debug(f"<-- RECV (ID: {request_id}): {json.dumps(response)}")
                if 'error' in response:
                    raise Exception(f"API Error (code {response['error']['code']}): {response['error']['message']}")
                return response.get('result')
            time.sleep(0.1)
        raise TimeoutError(f"Request {request_id} timed out. Please ensure you have accepted the prompt in the EMOTIV Launcher.")

    def _receive_loop(self):
        while self.ws and self.ws.connected:
            try:
                message = self.ws.recv()
                data = json.loads(message)
                
                # Handle RPC responses
                if 'id' in data:
                    self.responses[data['id']] = data
                # Handle data streams by passing the full data dict to the callback
                elif 'sid' in data and self.data_stream_callback:
                    logger.debug(f"<-- STREAM: {message}")
                    if any(key in data for key in ['eeg', 'pow', 'mot', 'dev', 'eq', 'met']):
                        self.data_stream_callback(data)
                # Handle warnings
                elif 'warning' in data:
                     logger.warning(f"Cortex Warning: {data['warning']['message']}")
                else:
                    logger.debug(f"<-- UNHANDLED: {message}")
            except websocket.WebSocketConnectionClosedException:
                logger.info("Cortex connection closed.")
                if self.on_disconnect_callback:
                    self.on_disconnect_callback()
                break
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")
                if self.on_disconnect_callback:
                    self.on_disconnect_callback()
                break

    def connect_and_authorize(self):
        """Step 1 of the flow: Connect, request access, and get headset list."""
        ssl_options = {}
        # The real Cortex API (wss) requires SSL. The local mock server (ws) does not.
        if self.url.startswith("wss://"):
            logger.info("Connecting with SSL for wss:// connection.")
            ssl_options = {"cert_reqs": ssl.CERT_NONE}
        else:
            logger.info("Connecting without SSL for ws:// connection (mock server).")

        try:
            # Connect without a timeout initially, to allow the user time to select a headset.
            self.ws = websocket.create_connection(self.url, sslopt=ssl_options)
            self.thread = threading.Thread(target=self._receive_loop)
            self.thread.daemon = True
            self.thread.start()
        except Exception as e:
            logger.error(f"Failed to connect to Cortex WebSocket at {self.url}: {e}")
            raise ConnectionRefusedError("Could not connect to EMOTIV Launcher. Is it running?") from e

        logger.info("Requesting access...")
        req_id = self._send_request('requestAccess', {'clientId': self.client_id, 'clientSecret': self.client_secret})
        self._wait_for_response(req_id)
        logger.info("Access granted by user.")

        logger.info("Querying headsets...")
        req_id = self._send_request('queryHeadsets')
        headsets = self._wait_for_response(req_id)
        if not headsets:
            raise ConnectionError("No headsets found. Is your device connected and turned on?")
        logger.info(f"Found {len(headsets)} headset(s).")
        return headsets

    def query_headsets(self):
        """Just queries the available headsets without changing connection state."""
        logger.info("Re-querying headsets...")
        req_id = self._send_request('queryHeadsets')
        headsets = self._wait_for_response(req_id)
        logger.info(f"Found {len(headsets)} headset(s).")
        return headsets

    def connect_to_headset(self, headset_id):
        """Step 2 of the flow: Connect to a specific headset and subscribe to data."""
        logger.info(f"Connecting to headset {headset_id}...")
        req_id = self._send_request('controlDevice', {'command': 'connect', 'headset': headset_id})
        self._wait_for_response(req_id)
        logger.info("Headset connected.")

        logger.info("Authorizing session...")
        req_id = self._send_request('authorize', {'clientId': self.client_id, 'clientSecret': self.client_secret})
        self.auth_token = self._wait_for_response(req_id)['cortexToken']
        logger.info("Authorization successful.")

        logger.info("Creating session...")
        req_id = self._send_request('createSession', {'cortexToken': self.auth_token, 'headset': headset_id, 'status': 'active'})
        self.session_id = self._wait_for_response(req_id)['id']
        logger.info(f"Session created: {self.session_id}")

        logger.info("Subscribing to band power data...")
        req_id = self._send_request('subscribe', {'cortexToken': self.auth_token, 'session': self.session_id, 'streams': ['pow']})
        self._wait_for_response(req_id)
        
        # Set a timeout to detect if the connection drops unexpectedly.
        self.ws.settimeout(5)
        
        logger.info("Successfully subscribed to EEG data stream.")

    def set_data_callback(self, callback):
        self.data_stream_callback = callback

    def set_disconnect_callback(self, callback):
        self.on_disconnect_callback = callback

    def is_session_active(self):
        """Checks if a session has been successfully created."""
        return self.session_id is not None


    def disconnect(self):
        if self.ws and self.ws.connected:
            self.ws.close()
            logger.info("Disconnected from Cortex.")

document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded and parsed. Initializing application.");
    // --- DOM Elements ---
    const connectBtn = document.getElementById('connect-btn');
    const disconnectBtn = document.getElementById('disconnect-btn');
    const statusIndicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    const logMessage = document.getElementById('log-message');

    // Main containers
    const initialScoreContainer = document.getElementById('initial-score-container');
    const headsetSelectionContainer = document.getElementById('headset-selection-container');
    const readyContainer = document.getElementById('ready-container');
    const recordingContainer = document.getElementById('recording-container');
    const resultsContainer = document.getElementById('results-container');

    // Interactive elements
    const headsetList = document.getElementById('headset-list');
    const headsetLoader = document.getElementById('headset-loader');
    const refreshBtn = document.getElementById('refresh-headsets-btn');
    const startRecordingBtn = document.getElementById('start-recording-btn');
    const newRecordingBtn = document.getElementById('new-recording-btn');
    const restartRecordingBtn = document.getElementById('restart-recording-btn');
    
    // Display elements
    const scoreLoader = document.getElementById('score-loader');
    const timerDisplay = document.getElementById('timer');
    const scoreValue = document.getElementById('score-value');
    const averageScoreDisplay = document.getElementById('average-score-value');

    // --- State ---
    let socket = null;
    let recordingTimer = null;
    let lastUIUpdateTime = 0;
    const UI_UPDATE_INTERVAL = 1000;
    
    let headsetPollInterval = null;
    let pollCounter = 0;
    const MAX_POLLS = 3;

    // --- UI State Management ---
    const showMessage = (message, isError = false) => {
        logMessage.textContent = message;
        logMessage.style.color = isError ? '#e74c3c' : '#95a5a6';
        if (isError) {
            console.error(`UI Message (Error): ${message}`);
        } else {
            console.log(`UI Message: ${message}`);
        }
    };
    
    const stopHeadsetPolling = () => {
        if (headsetPollInterval) {
            console.log("Stopping headset polling.");
            clearInterval(headsetPollInterval);
            headsetPollInterval = null;
        }
        headsetLoader.style.display = 'none';
        refreshBtn.disabled = false;
    };

    const setUIState = (state) => {
        console.log(`%cSetting UI state to: ${state}`, 'color: #007bff; font-weight: bold;');
        
        if (state !== 'selecting_headset') {
            stopHeadsetPolling();
        }

        // Hide all main containers by default
        initialScoreContainer.style.display = 'none';
        headsetSelectionContainer.style.display = 'none';
        readyContainer.style.display = 'none';
        recordingContainer.style.display = 'none';
        resultsContainer.style.display = 'none';
        
        // Reset loading states on main button
        connectBtn.classList.remove('loading');


        if (state === 'disconnected') {
            statusIndicator.className = 'disconnected';
            statusText.textContent = 'Disconnected';
            connectBtn.disabled = false;
            disconnectBtn.disabled = true;
            initialScoreContainer.style.display = 'block';
            scoreLoader.style.display = 'none';
            showMessage('Welcome! Click "Connect" to start.');
        } else if (state === 'connecting') {
            statusText.textContent = 'Connecting...';
            connectBtn.disabled = true;
            disconnectBtn.disabled = true;
            connectBtn.classList.add('loading');
        } else if (state === 'selecting_headset') {
            statusIndicator.className = 'disconnected';
            statusText.textContent = 'Disconnected';
            headsetSelectionContainer.style.display = 'block';
            connectBtn.disabled = true;
            disconnectBtn.disabled = false;
            showMessage('Please select a headset from the list below.');
            startHeadsetPolling();
        } else if (state === 'connecting_headset') {
            statusText.textContent = 'Connecting to Headset...';
            // No main content shown here, just the status text.
            // The spinner is on the list item itself.
            connectBtn.disabled = true;
            disconnectBtn.disabled = false;
        } else if (state === 'ready') {
            statusIndicator.className = 'connected';
            statusText.textContent = 'Device Ready';
            readyContainer.style.display = 'block';
            connectBtn.disabled = true;
            disconnectBtn.disabled = false;
            showMessage('Select duration and start recording.');
        } else if (state === 'recording') {
            statusText.textContent = 'Recording...';
            recordingContainer.style.display = 'block';
        } else if (state === 'results') {
            statusIndicator.className = 'connected';
            statusText.textContent = 'Device Ready';
            resultsContainer.style.display = 'block';
        }
    };

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `Time Left: ${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    };

    // --- WebSocket Handling ---
    const setupWebSocket = () => {
        if (socket && socket.connected) {
            console.log("WebSocket already connected.");
            return;
        }
        console.log(`Attempting to connect WebSocket to http://${document.domain}:${location.port}`);
        socket = io.connect(`http://${document.domain}:${location.port}`, { reconnection: false });

        socket.on('connect', () => {
            console.log(`%cWebSocket connected with SID: ${socket.id}`, 'color: green;');
        });

        socket.on('disconnect', () => {
            console.warn("WebSocket disconnected.");
            if (recordingTimer) clearInterval(recordingTimer);
            setUIState('disconnected');
            showMessage('Connection to server lost.');
        });
        
        socket.on('recording_started', (data) => {
            console.log('Received "recording_started" event.', data);
            setUIState('recording');
            let timeLeft = data.duration;
            timerDisplay.textContent = formatTime(timeLeft);
            scoreValue.textContent = '--';

            recordingTimer = setInterval(() => {
                timeLeft--;
                timerDisplay.textContent = formatTime(timeLeft);
                if (timeLeft <= 0) clearInterval(recordingTimer);
            }, 1000);
        });

        socket.on('new_score', (data) => {
            const now = Date.now();
            if (now - lastUIUpdateTime > UI_UPDATE_INTERVAL) {
                console.log('Received "new_score" event:', data);
                scoreValue.textContent = data.score;
                lastUIUpdateTime = now;
            }
        });
        
        socket.on('recording_ended', (data) => {
            console.log('Received "recording_ended" event:', data);
            if (recordingTimer) clearInterval(recordingTimer);
            setUIState('results');
            averageScoreDisplay.textContent = data.average_score;
            showMessage(`Recording complete.`);
        });

        socket.on('recording_cancelled', () => {
            console.log('Received "recording_cancelled" event.');
            if (recordingTimer) clearInterval(recordingTimer);
            setUIState('ready');
            showMessage('Recording cancelled. Please select a new duration.');
        });

        socket.on('server_disconnected', (data) => {
            console.error('Received "server_disconnected" event from backend:', data);
            if (recordingTimer) clearInterval(recordingTimer);
            setUIState('disconnected');
            showMessage(`Error: ${data.message}`, true);
        });
    };

    // --- API Call Functions ---
    const startHeadsetPolling = () => {
        console.log("Starting headset polling...");
        stopHeadsetPolling();
        pollCounter = 0;
        headsetLoader.style.display = 'block';
        refreshBtn.disabled = true;
        headsetList.innerHTML = '<li>Searching for headsets...</li>';

        const poll = async () => {
            pollCounter++;
            console.log(`Polling for headsets... (Attempt ${pollCounter}/${MAX_POLLS})`);
            try {
                const response = await fetch('/api/headsets');
                const data = await response.json();
                console.log("Poll response:", data);
                if (response.ok && data.headsets && data.headsets.length > 0) {
                    displayHeadsetList(data.headsets);
                }
            } catch (error) { console.error('Error during headset poll:', error); }

            if (pollCounter >= MAX_POLLS) {
                console.log("Max polls reached. Stopping.");
                stopHeadsetPolling();
                if (headsetList.innerHTML.includes('Searching')) {
                     headsetList.innerHTML = '<li>No headsets found. Click ⟳ to search again.</li>';
                }
            }
        };

        headsetPollInterval = setInterval(poll, 1000);
        poll();
    };
    
    const connect = async () => {
        console.log("Calling API: /api/connect");
        setUIState('connecting');
        try {
            const response = await fetch('/api/connect', { method: 'POST' });
            if (response.ok) {
                console.log("API /api/connect successful.");
                setUIState('selecting_headset');
            } else {
                const data = await response.json();
                throw new Error(data.message || 'Failed to connect.');
            }
        } catch (error) {
            console.error("Error in connect():", error);
            setUIState('disconnected');
            showMessage(`Error: ${error.message}`, true);
        }
    };

    const displayHeadsetList = (headsets) => {
        console.log("Displaying headset list:", headsets);
        headsetList.innerHTML = '';
        headsets.forEach(headset => {
            const li = document.createElement('li');
            li.innerHTML = `<span class="btn-text">${headset.customName || headset.id}</span>
                            <span class="spinner" style="display: none;"></span>`;
            li.dataset.headsetId = headset.id;
            li.addEventListener('click', () => selectHeadset(li, headset.id));
            headsetList.appendChild(li);
        });
    };

    const selectHeadset = async (listItem, headsetId) => {
        console.log(`Calling API: /api/select_headset with ID: ${headsetId}`);
        // Disable all items and show spinner on the clicked one
        document.querySelectorAll('#headset-list li').forEach(li => li.classList.add('disabled'));
        listItem.classList.remove('disabled');
        listItem.classList.add('loading');

        stopHeadsetPolling();
        setUIState('connecting_headset');
        try {
            const response = await fetch('/api/select_headset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ headsetId }),
            });
            if (response.ok) {
                console.log("API /api/select_headset successful.");
                setUIState('ready');
                setupWebSocket();
            } else {
                const data = await response.json();
                throw new Error(data.message || 'Failed to connect to headset.');
            }
        } catch (error) {
            console.error("Error in selectHeadset():", error);
            setUIState('disconnected');
            showMessage(`Error: ${error.message}`, true);
        }
    };
    
    const startRecording = async () => {
        const minutes = parseInt(document.getElementById('minutes-input').value, 10) || 0;
        const seconds = parseInt(document.getElementById('seconds-input').value, 10) || 0;
        const duration = (minutes * 60) + seconds;
        console.log(`Calling API: /api/start_recording with duration: ${duration}s`);

        if (duration <= 0) {
            showMessage('Please enter a valid duration.', true);
            return;
        }

        try {
            const response = await fetch('/api/start_recording', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ duration }),
            });
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.message || 'Failed to start recording.');
            }
            console.log("API /api/start_recording successful.");
        } catch (error) {
            console.error("Error in startRecording():", error);
            setUIState('ready');
            showMessage(`Error: ${error.message}`, true);
        }
    };

    const restartRecording = async () => {
        console.log("Calling API: /api/restart_recording");
        showMessage('Restarting recording...');
        try {
            await fetch('/api/restart_recording', { method: 'POST' });
            console.log("API /api/restart_recording successful.");
        } catch (error) {
            console.error("Error in restartRecording():", error);
            showMessage('Failed to restart recording.', true);
        }
    };

    const disconnect = async () => {
        console.log("User initiated disconnect.");
        if (socket) {
            console.log("Disconnecting WebSocket.");
            socket.disconnect();
        }
        console.log("Calling API: /api/disconnect");
        await fetch('/api/disconnect', { method: 'POST' });
        stopHeadsetPolling();
        if (recordingTimer) clearInterval(recordingTimer);
        setUIState('disconnected');
    };

    // --- Event Listeners ---
    console.log("Attaching event listeners.");
    connectBtn.addEventListener('click', connect);
    disconnectBtn.addEventListener('click', disconnect);
    refreshBtn.addEventListener('click', startHeadsetPolling);
    startRecordingBtn.addEventListener('click', startRecording);
    newRecordingBtn.addEventListener('click', () => setUIState('ready'));
    restartRecordingBtn.addEventListener('click', restartRecording);

    window.addEventListener('beforeunload', () => {
        if (!disconnectBtn.disabled) {
            console.log("Sending beacon on page unload to disconnect.");
            navigator.sendBeacon('/api/disconnect', new Blob());
        }
    });

    // --- Initial State ---
    console.log("Setting initial UI state.");
    setUIState('disconnected');
});

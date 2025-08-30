const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const waitOn = require('wait-on');
const fs = require('fs');
const os = require('os');

// --- Injected via GitHub Actions at build time ---
const secrets = {
  CLIENT_ID: 'YOUR_CLIENT_ID_PLACEHOLDER',
  CLIENT_SECRET: 'YOUR_CLIENT_SECRET_PLACEHOLDER',
  USE_MOCK_SERVER: 'false',
  LOG_VERBOSE: '2',
};
// ----------------------------------------------------

let backend = null;

function getResourcesRoot() {
  // In a packaged app, the resources directory is at process.resourcesPath
  // In development, it's just the current directory ('desktop')
  return app.isPackaged
    ? process.resourcesPath
    : __dirname;
}

function getBackendExecutablePath() {
  const resourcesRoot = getResourcesRoot();
  const exeName = process.platform === 'win32' ? 'backend_executable.exe' : 'backend_executable';
  
  // With PyInstaller's directory output, the executable is inside a folder
  // that has the same name.
  // Final path: <resources>/backend_executable/backend_executable
  return path.join(resourcesRoot, 'backend_executable', exeName);
}

async function startBackend() {
  const backendExecutable = getBackendExecutablePath();
  
  console.log('Starting backend with executable:');
  console.log('Executable path:', backendExecutable);

  // --- macOS Gatekeeper Fix ---
  // On macOS, files downloaded from the internet get a "quarantine" attribute.
  // This can prevent our unsigned backend executable from running, causing an EACCES error.
  // We explicitly remove this attribute before trying to execute it.
  if (process.platform === 'darwin' && app.isPackaged) {
    try {
      const { execSync } = require('child_process');
      const command = `xattr -cr "${backendExecutable}"`;
      console.log(`[Gatekeeper Fix] Running command: ${command}`);
      execSync(command);
      console.log(`[Gatekeeper Fix] Successfully removed quarantine attribute.`);
    } catch (error) {
      console.error(`[Gatekeeper Fix] Failed to remove quarantine attribute:`, error);
      // We'll still try to launch, but it might fail.
    }
  }

  const portPref = process.env.PORT || '5000';
  const getFreePort = async (start) => {
    try {
      const detect = require('detect-port');
      const free = await detect(parseInt(start, 10));
      return String(free);
    } catch (_) {
      return start;
    }
  };
  const port = await getFreePort(portPref);
  // On macOS, the app bundle path is not writable. Use userData for logs/data.
  // On other platforms, using the exe's directory is fine.
  const runCwd = process.platform === 'darwin'
    ? path.join(app.getPath('userData'), 'AlumenEEG')
    : path.dirname(process.execPath);
  fs.mkdirSync(runCwd, { recursive: true });

  // Dynamically create a config.py override with secrets injected at build time.
  // This avoids storing secrets in the packaged source code.
  const tmpConfDir = fs.mkdtempSync(path.join(os.tmpdir(), 'mvp-conf-'));
  const parseBool = (val, def) => {
    if (val === undefined || val === null || String(val).trim() === '') return def;
    const v = String(val).trim().toLowerCase();
    if (["1","true","yes","y","on"].includes(v)) return true;
    if (["0","false","no","n","off"].includes(v)) return false;
    return def;
  };
  const useMock = parseBool(secrets.USE_MOCK_SERVER, false);
  const clientId = secrets.CLIENT_ID || 'YOUR_CLIENT_ID';
  const clientSecret = secrets.CLIENT_SECRET || 'YOUR_CLIENT_SECRET';
  const cfgContent = `# Auto-generated at runtime by Electron wrapper\nUSE_MOCK_SERVER = ${useMock ? 'True' : 'False'}\nUSER_CONFIG = {\n  "client_id": "${clientId}",\n  "client_secret": "${clientSecret}",\n  "cortex_url": "ws://localhost:6868" if USE_MOCK_SERVER else "wss://localhost:6868"\n}\n`;
  fs.writeFileSync(path.join(tmpConfDir, 'config.py'), cfgContent);

  // Since we are using a self-contained PyInstaller executable, we no longer need
  // to set up a complex Python environment with DYLD_LIBRARY_PATH, etc.
  // We only need to provide our temporary config path via PYTHONPATH.
   const childEnv = {
     ...process.env,
     OPEN_BROWSER: '0',
     PORT: port,
     CLIENT_ID: clientId,
     CLIENT_SECRET: clientSecret,
     USE_MOCK_SERVER: useMock ? '1' : '0',
     LOG_VERBOSE: secrets.LOG_VERBOSE || '2',
     // By setting PYTHONPATH, the bundled Python script can find our generated config.
     PYTHONPATH: tmpConfDir,
   };

  console.log('Spawning backend process with CWD:', runCwd);
  
  backend = spawn(backendExecutable, [], {
    cwd: runCwd,
    env: childEnv,
    stdio: ['inherit', 'pipe', 'pipe'],
    windowsHide: true,
  });

  // Capture and log stdout and stderr
  backend.stdout.on('data', (data) => {
    console.log('Backend stdout:', data.toString());
  });

  backend.stderr.on('data', (data) => {
    console.error('Backend stderr:', data.toString());
  });

  backend.on('error', (err) => {
    console.error('Failed to start backend:', err);
  });

  backend.on('exit', (code, signal) => {
    console.log('Backend process exited with code:', code, 'signal:', signal);
  });

  await waitOn({ resources: [`http://127.0.0.1:${port}`], timeout: 30000 });
  return port;
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    show: false, // Don't show the window until it's ready
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    }
  });

  // Show a loading screen immediately
  await win.loadFile(path.join(__dirname, 'splash.html'));
  win.show();

  // Start the backend in the background and load the real URL when ready
  startBackend().then(port => {
    console.log('Backend started successfully on port:', port);
    win.loadURL(`http://127.0.0.1:${port}`);
  }).catch(err => {
    console.error("Failed to start backend:", err);
    // Show error in splash window
    win.webContents.executeJavaScript(`
      document.getElementById('status').innerHTML = 'Error: ${err.message || 'Failed to start backend'}';
      document.getElementById('status').style.color = 'red';
    `);
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (backend && !backend.killed) backend.kill();
});
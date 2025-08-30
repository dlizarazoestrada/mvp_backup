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
  return app.isPackaged
    ? process.resourcesPath
    : __dirname;
}

function getBackendExecutablePath() {
  const resourcesRoot = getResourcesRoot();
  const exeName = process.platform === 'win32' ? 'backend_executable.exe' : 'backend_executable';
  // The executable is now placed in a 'backend' folder inside resources
  return path.join(resourcesRoot, 'backend', exeName);
}

function getPythonEnvRoot() {
  return path.join(getResourcesRoot(), 'python-env');
}

function getPythonExecutable() {
  const envRoot = getPythonEnvRoot();
  if (process.platform === 'win32') {
    const pythonw = path.join(envRoot, 'pythonw.exe');
    if (fs.existsSync(pythonw)) return pythonw; // no console window
    return path.join(envRoot, 'python.exe');
  }
  return path.join(envRoot, 'bin', 'python');
}

function getAppRoot() {
  // where backend/ and frontend/ are placed inside the packaged app
  return path.join(getResourcesRoot(), 'app');
}

async function startBackend() {
  const backendExecutable = getBackendExecutablePath();
  
  console.log('Starting backend with executable:');
  console.log('Executable path:', backendExecutable);

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
  // On macOS, the app bundle path is not writable. Use userData; on Windows keep exe dir.
  const runCwd = process.platform === 'darwin'
    ? path.join(app.getPath('userData'), 'AlumenEEG')
    : path.dirname(process.execPath);
  fs.mkdirSync(runCwd, { recursive: true });
  // Create a temporary config.py override if env vars are provided
  const tmpConfDir = fs.mkdtempSync(path.join(os.tmpdir(), 'mvp-conf-'));
  const hasSecrets = (secrets.CLIENT_ID) && (secrets.CLIENT_SECRET);
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

     // Prepare environment variables for Python
   const pythonEnvRoot = getPythonEnvRoot();
   const pythonLibPath = path.join(pythonEnvRoot, 'lib');
   
   // Special handling for macOS paths - Create a completely isolated environment
   const macOSPaths = process.platform === 'darwin' ? {
     // Force the dynamic linker to ONLY look inside our bundled Python environment
     DYLD_LIBRARY_PATH: [
       pythonLibPath,
       path.join(pythonLibPath, '.dylibs'),
       path.join(pythonLibPath, 'lib'),
     ].filter(Boolean).join(path.delimiter),
     
     // Point to our frameworks, ignoring the system ones
     DYLD_FRAMEWORK_PATH: pythonLibPath,

     PYTHONHOME: pythonEnvRoot,
     LC_ALL: 'en_US.UTF-8',
     LANG: 'en_US.UTF-8',
     VECLIB_MAXIMUM_THREADS: '1',  // Prevent threading issues
   } : {};

   const childEnv = {
     ...process.env,
     OPEN_BROWSER: '0',
     PORT: port,
     CLIENT_ID: clientId,
     CLIENT_SECRET: clientSecret,
     USE_MOCK_SERVER: useMock ? '1' : '0',
     LOG_VERBOSE: secrets.LOG_VERBOSE || '2',
     // We need to clear the inherited PYTHONPATH to ensure only our paths are used
     PYTHONPATH: [
       tmpConfDir,
       path.join(pythonEnvRoot, 'lib/python3.9/site-packages'),
     ].filter(Boolean).join(path.delimiter),
     ...macOSPaths
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
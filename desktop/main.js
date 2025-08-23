const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const waitOn = require('wait-on');
const fs = require('fs');
const os = require('os');

// Load .env if present (root or desktop folder)
try {
  const dotenv = require('dotenv');
  const rootEnv = path.join(__dirname, '..', '.env');
  const localEnv = path.join(__dirname, '.env');
  if (fs.existsSync(rootEnv)) dotenv.config({ path: rootEnv });
  else if (fs.existsSync(localEnv)) dotenv.config({ path: localEnv });
} catch (_) { /* optional */ }

let backend = null;

function getResourcesRoot() {
  return app.isPackaged
    ? process.resourcesPath
    : path.join(__dirname);
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
  const python = getPythonExecutable();
  const appRoot = getAppRoot();
  const scriptPath = path.join(appRoot, 'backend', 'main.py');
  
  console.log('Starting backend with:');
  console.log('Python executable:', python);
  console.log('App root:', appRoot);
  console.log('Script path:', scriptPath);
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
  const hasSecrets = (process.env.CLIENT_ID || process.env.EMOTIV_CLIENT_ID) && (process.env.CLIENT_SECRET || process.env.EMOTIV_CLIENT_SECRET);
  const parseBool = (val, def) => {
    if (val === undefined || val === null || String(val).trim() === '') return def;
    const v = String(val).trim().toLowerCase();
    if (["1","true","yes","y","on"].includes(v)) return true;
    if (["0","false","no","n","off"].includes(v)) return false;
    return def;
  };
  const useMock = parseBool(process.env.USE_MOCK_SERVER, true);
  const clientId = process.env.CLIENT_ID || process.env.EMOTIV_CLIENT_ID || 'YOUR_CLIENT_ID';
  const clientSecret = process.env.CLIENT_SECRET || process.env.EMOTIV_CLIENT_SECRET || 'YOUR_CLIENT_SECRET';
  const cfgContent = `# Auto-generated at runtime by Electron wrapper\nUSE_MOCK_SERVER = ${useMock ? 'True' : 'False'}\nUSER_CONFIG = {\n  "client_id": "${clientId}",\n  "client_secret": "${clientSecret}",\n  "cortex_url": "ws://localhost:6868" if USE_MOCK_SERVER else "wss://localhost:6868"\n}\n`;
  fs.writeFileSync(path.join(tmpConfDir, 'config.py'), cfgContent);

     // Prepare environment variables for Python
   const pythonEnvRoot = getPythonEnvRoot();
   const pythonLibPath = path.join(pythonEnvRoot, 'lib');
   
   // Special handling for macOS paths
   const macOSPaths = process.platform === 'darwin' ? {
     DYLD_LIBRARY_PATH: [
       pythonLibPath,
       path.join(pythonLibPath, 'python3.11'),
       path.join(pythonLibPath, 'python3.11/lib-dynload'),
       path.join(pythonLibPath, '.dylibs'),  // Add .dylibs directory
       '/usr/lib',  // Add system libraries
       process.env.DYLD_LIBRARY_PATH
     ].filter(Boolean).join(path.delimiter),
     DYLD_FRAMEWORK_PATH: pythonLibPath,
     PYTHONHOME: pythonEnvRoot,
     LC_ALL: 'en_US.UTF-8',
     LANG: 'en_US.UTF-8',
   } : {};

   const childEnv = {
     ...process.env,
     OPEN_BROWSER: '0',
     PORT: port,
     CLIENT_ID: clientId,
     CLIENT_SECRET: clientSecret,
     USE_MOCK_SERVER: useMock ? '1' : '0',
     LOG_VERBOSE: process.env.LOG_VERBOSE || '2',
     PYTHONPATH: [
       tmpConfDir,
       path.join(pythonEnvRoot, 'lib/python3.11/site-packages'),
       process.env.PYTHONPATH
     ].filter(Boolean).join(path.delimiter),
     ...macOSPaths
   };

  console.log('Spawning backend process with CWD:', runCwd);
  
  backend = spawn(python, [scriptPath], {
    cwd: runCwd,
    env: childEnv,
    stdio: 'inherit',
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
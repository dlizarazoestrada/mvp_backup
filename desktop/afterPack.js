// desktop/afterPack.js
const fs = require('fs');
const path = require('path');

/**
 * This script is executed by electron-builder after it has packed the application.
 * Its purpose is to manually set the execute permissions on our Python backend
 * executable, as these permissions can sometimes be lost during the packaging process.
 * This is a crucial step to prevent EACCES (Permission Denied) errors on macOS.
 */
exports.default = async function(context) {
  const { appOutDir, packager } = context;
  const appName = packager.appInfo.productFilename;
  const platform = packager.platform.name;

  // We only need to do this on macOS
  if (platform === 'mac') {
    // Define the path to our executable within the final .app bundle.
    // Note: This must match the structure defined by PyInstaller and electron-builder.
    const executablePath = path.join(
      appOutDir,
      `${appName}.app`,
      'Contents',
      'Resources',
      'backend_executable', // This is the FOLDER
      'backend_executable'  // This is the EXECUTABLE inside the folder
    );
    
    console.log(`[afterPack] Ensuring execute permissions for: ${executablePath}`);
    
    if (fs.existsSync(executablePath)) {
      try {
        // Set permissions to rwxr-xr-x (read, write, execute for owner; read, execute for group and others)
        fs.chmodSync(executablePath, 0o755);
        console.log(`[afterPack] Successfully set execute permissions on backend_executable.`);
      } catch (error) {
        console.error(`[afterPack] Failed to set permissions on backend_executable:`, error);
        // Fail the build if we can't set the permissions, as the app will be broken
        throw error;
      }
    } else {
      console.warn(`[afterPack] backend_executable not found at path: ${executablePath}. Skipping chmod.`);
    }
  }
};

const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const ROOT = path.join(__dirname, "..");
const isWin = process.platform === "win32";

let backend = null;

function backendCommand() {
  if (app.isPackaged) {
    // Packaged: run the frozen standalone backend (PyInstaller) bundled as an
    // unpacked resource — no system Python required. electron-builder copies
    // pybuild/dist/garmin-backend -> <resources>/backend/.
    const exe = path.join(
      process.resourcesPath, "backend",
      isWin ? "garmin-backend.exe" : "garmin-backend"
    );
    return { cmd: exe, args: [], cwd: path.dirname(exe) };
  }
  // Dev: run from the project venv (falling back to system python).
  const py = path.join(ROOT, ".venv", isWin ? "Scripts/python.exe" : "bin/python");
  const cmd = fs.existsSync(py) ? py : (isWin ? "python" : "python3");
  return { cmd, args: ["-m", "backend.api"], cwd: ROOT };
}

function startBackend() {
  const { cmd, args, cwd } = backendCommand();
  // Per-user state (DB, token store, capability profile, settings, log) is
  // written to the OS user-data dir, not the app folder, so one installed build
  // serves any user without writing into its own directory.
  backend = spawn(cmd, args, {
    cwd,
    stdio: app.isPackaged ? "ignore" : "inherit",
    env: { ...process.env, GARMIN_DASH_DATA_DIR: app.getPath("userData") },
  });
  backend.on("exit", (code) => console.log("backend exited", code));
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1100, height: 800, backgroundColor: "#0a0a0a",
    webPreferences: { contextIsolation: true },
  });
  win.loadFile(path.join(ROOT, "frontend", "dist", "index.html"));
}

app.whenReady().then(() => {
  startBackend();
  // give Flask a moment to bind before the window fetches
  setTimeout(createWindow, 1500);
});

function killBackend() {
  if (backend && !backend.killed) backend.kill();
}
app.on("window-all-closed", () => { killBackend(); app.quit(); });
app.on("before-quit", killBackend);
process.on("exit", killBackend);

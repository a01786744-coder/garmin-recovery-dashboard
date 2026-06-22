const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const ROOT = path.join(__dirname, "..");
const isWin = process.platform === "win32";
const PY = path.join(ROOT, ".venv", isWin ? "Scripts/python.exe" : "bin/python");

let backend = null;

function startBackend() {
  const py = fs.existsSync(PY) ? PY : (isWin ? "python" : "python3");
  // Per-user state (DB, token store, capability profile, settings, log) is
  // written to the OS user-data dir, not the project folder, so one installed
  // build serves any user without writing into its own directory.
  backend = spawn(py, ["-m", "backend.api"], {
    cwd: ROOT,
    stdio: "inherit",
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

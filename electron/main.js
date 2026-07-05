const { app, BrowserWindow, Tray, Menu, nativeImage, shell } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const ROOT = path.join(__dirname, "..");
const isWin = process.platform === "win32";

let backend = null;
let win = null;
let tray = null;
let quitting = false;

// One instance only: launching the app again (e.g. from the desktop shortcut
// while it lives in the tray) focuses the existing window instead of spawning
// a second backend that would fight over port 5057.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => showWindow());
}

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
    env: {
      ...process.env,
      GARMIN_DASH_DATA_DIR: app.getPath("userData"),
      // Where the backend finds the built frontend to serve. Packaged: the
      // extraResource copy; dev: the repo's frontend/dist.
      GARMIN_DASH_STATIC: app.isPackaged
        ? path.join(process.resourcesPath, "frontend")
        : path.join(ROOT, "frontend", "dist"),
    },
  });
  backend.on("exit", (code) => console.log("backend exited", code));
}

// --- settings.json (backend-owned) drives the login item ---

function settingsPath() {
  return path.join(app.getPath("userData"), "settings.json");
}

function readSettings() {
  try {
    return JSON.parse(fs.readFileSync(settingsPath(), "utf-8"));
  } catch (e) {
    return {};
  }
}

function applyLoginItem() {
  const s = readSettings();
  app.setLoginItemSettings({
    openAtLogin: !!s.start_at_login,
    openAsHidden: true,      // macOS hint
    args: ["--hidden"],      // Windows: detected below to start minimized
  });
}

function watchSettings() {
  // Watch the directory: the backend rewrites settings.json atomically, and
  // watching the file itself would drop after the first replace.
  try {
    fs.watch(path.dirname(settingsPath()), (evt, name) => {
      if (name === "settings.json") applyLoginItem();
    });
  } catch (e) {
    /* watching is best-effort; the setting still applies on next launch */
  }
}

// --- window & tray ---

function trayIcon() {
  const p = app.isPackaged
    ? path.join(process.resourcesPath, "frontend", "icon-192.png")
    : path.join(ROOT, "frontend", "public", "icon-192.png");
  const img = nativeImage.createFromPath(p);
  return img.isEmpty() ? img : img.resize({ width: 16, height: 16 });
}

function createTray() {
  tray = new Tray(trayIcon());
  tray.setToolTip("Garmin Recovery Dashboard");
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "Open Dashboard", click: () => showWindow() },
    { type: "separator" },
    { label: "Quit", click: () => { quitting = true; app.quit(); } },
  ]));
  tray.on("click", () => showWindow());
}

function createWindow(show) {
  win = new BrowserWindow({
    width: 1100, height: 800, backgroundColor: "#0a0a0a",
    show,
    webPreferences: { contextIsolation: true },
  });
  // The backend serves the SPA; load it by URL (same origin as the API) and
  // retry until the server has bound its port.
  const load = () => win.loadURL("http://127.0.0.1:5057/").catch(() => setTimeout(load, 400));
  load();
  // Open external links (e.g. the update-notifier Download link) in the user's
  // real browser instead of a new Electron window.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) {
      shell.openExternal(url);
      return { action: "deny" };
    }
    return { action: "allow" };
  });
  // Closing the window keeps the app (and backend) alive in the tray so the
  // phone dashboard stays reachable; Quit in the tray menu really exits.
  win.on("close", (e) => {
    if (!quitting) {
      e.preventDefault();
      win.hide();
    }
  });
}

function showWindow() {
  if (win && !win.isDestroyed()) {
    win.show();
    win.focus();
  } else {
    createWindow(true);
  }
}

app.whenReady().then(() => {
  startBackend();
  applyLoginItem();
  watchSettings();
  createTray();
  const startHidden = process.argv.includes("--hidden")
    || app.getLoginItemSettings().wasOpenedAsHidden;
  // give Flask a moment to bind before the window fetches
  setTimeout(() => createWindow(!startHidden), 1500);
});

// macOS: clicking the dock icon re-opens the hidden window.
app.on("activate", () => showWindow());

function killBackend() {
  if (backend && !backend.killed) backend.kill();
}

// Windows stay-alive: closing the window hides it (see 'close' handler), so
// this only fires if the window is truly destroyed — keep running in the tray.
app.on("window-all-closed", () => { /* stay alive in the tray */ });
app.on("before-quit", () => { quitting = true; killBackend(); });
process.on("exit", killBackend);

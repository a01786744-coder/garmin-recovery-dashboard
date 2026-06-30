// Cross-platform PyInstaller freeze of the Python backend into a standalone
// `garmin-backend` (onedir). Picks the right interpreter so the same npm script
// works locally (project .venv) and in CI (system python from setup-python):
//   1. $PYTHON if set (CI can pin the exact interpreter)
//   2. the project .venv (Scripts/python.exe on Windows, bin/python elsewhere)
//   3. the platform default (`python` on Windows, `python3` otherwise)
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const isWin = process.platform === "win32";
const venvPy = path.join(ROOT, ".venv", isWin ? "Scripts/python.exe" : "bin/python");
const python =
  process.env.PYTHON || (fs.existsSync(venvPy) ? venvPy : isWin ? "python" : "python3");

// Mirrors the original one-line command. --collect-all pulls in garminconnect and
// its native deps (curl_cffi) so the frozen backend needs no system Python.
const args = [
  "-m", "PyInstaller", "--noconfirm", "--onedir", "--name", "garmin-backend",
  "--distpath", "pybuild/dist", "--workpath", "pybuild/build", "--specpath", "pybuild",
  "--collect-all", "garminconnect",
  "--collect-all", "curl_cffi",
  "--collect-all", "ua_generator",
  "--collect-data", "certifi",
  "--collect-submodules", "backend",
  "server_main.py",
];

console.log(`[freeze] interpreter: ${python}`);
const res = spawnSync(python, args, { stdio: "inherit", cwd: ROOT });
if (res.error) {
  console.error(`[freeze] failed to launch: ${res.error.message}`);
  process.exit(1);
}
process.exit(res.status === null ? 1 : res.status);

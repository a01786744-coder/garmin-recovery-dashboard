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
// The AI coach needs the anthropic SDK AND its runtime deps: pydantic +
// pydantic_core and jiter are compiled/lazy-imported and were dropped in a CI
// build when relying on anthropic's import graph alone, so collect them
// explicitly and copy anthropic's metadata (its __version__ reads it).
const args = [
  "-m", "PyInstaller", "--noconfirm", "--onedir", "--name", "garmin-backend",
  "--distpath", "pybuild/dist", "--workpath", "pybuild/build", "--specpath", "pybuild",
  "--collect-all", "garminconnect",
  "--collect-all", "curl_cffi",
  "--collect-all", "ua_generator",
  "--collect-all", "anthropic",   // v4.0 AI coach (Claude API client)
  "--collect-all", "pydantic",
  "--collect-all", "pydantic_core",
  "--collect-all", "jiter",
  "--collect-all", "httpx",
  "--collect-all", "httpcore",
  "--collect-all", "anyio",
  "--collect-all", "distro",
  "--copy-metadata", "anthropic",
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
if (res.status !== 0) {
  process.exit(res.status === null ? 1 : res.status);
}

// Guard: never ship a bundle silently missing a critical package. A prior CI
// build dropped the anthropic SDK (coach failed at runtime with
// ModuleNotFoundError) even though PyInstaller reported success — fail the
// build loudly here instead so a broken coach can never reach a release.
const internal = path.join(ROOT, "pybuild", "dist", "garmin-backend", "_internal");
const required = ["garminconnect", "anthropic", "pydantic", "pydantic_core", "jiter"];
const missing = required.filter((pkg) => !fs.existsSync(path.join(internal, pkg)));
if (missing.length) {
  console.error(`[freeze] FATAL: frozen bundle is missing packages: ${missing.join(", ")}`);
  console.error(`[freeze] (checked ${internal})`);
  process.exit(1);
}
console.log(`[freeze] verified bundled packages: ${required.join(", ")}`);
process.exit(0);

# Phone Access (LAN + Tailscale, PWA) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the owner open the existing dashboard on their iPhone over home Wi‑Fi and Tailscale, installable to the home screen, with the app's data staying on the PC.

**Architecture:** The Flask backend starts serving the built React SPA *and* the API from one origin (`http://<pc>:5057/`); Electron loads that URL instead of a `file://`, and the frontend switches to same‑origin calls. A settings toggle binds the server to all interfaces (LAN + Tailscale) and a required access PIN gates every non‑loopback API request. A web manifest + Apple meta tags + secure‑context service worker make it installable on iOS.

**Tech Stack:** Python 3.11 / Flask 3, React + Vite + Tailwind, Electron 31 / electron‑builder, PyInstaller, Pillow (icon generation), Tailscale (user‑installed, no code).

## Global Constraints

- Local‑first: no cloud, no accounts. Data/tokens never leave the PC. (verbatim intent from spec)
- Loopback requests (`127.0.0.1`, `::1`) require **no** PIN; every other remote address requires a valid `X-Access-Pin` on `/api/*`. Empty configured PIN ⇒ all non‑loopback API access denied.
- Never log the PIN or Garmin tokens (extend existing redaction; don't add new logging of secrets).
- Service worker registers **only** in a secure context (`window.isSecureContext`); iOS home‑screen install must work over plain HTTP without it (Apple meta tags).
- Keep `garminconnect==0.3.2` / Python 3.11; no new runtime Python deps. Existing **110 backend tests stay green**.
- Desktop Electron behavior unchanged for the user (loads locally, needs no PIN).

**Repo:** `C:\Users\rodri\Documents\garmin-dashboard`. Branch: `build-dashboard`. Run backend tests with `.venv/Scripts/python -m pytest backend -q`.

---

## File Structure

- `backend/settings.py` — add `phone_access` (bool) + `access_pin` (str) settings.
- `backend/config.py` — add `resolve_static_dir()` and `resolve_host(settings)`.
- `backend/api.py` — PIN `before_request` gate; static/SPA routes; `main()` binds via `resolve_host`.
- `backend/tests/test_phone_access.py` — new tests for settings, PIN gate, static serving, host.
- `frontend/src/api.js` — same‑origin `BASE`; attach `X-Access-Pin`; export a 401 signal.
- `frontend/src/PinGate.jsx` — new PIN entry screen.
- `frontend/src/App.jsx` — show `PinGate` on API 401.
- `frontend/vite.config.js` — dev proxy `/api` → `127.0.0.1:5057`.
- `frontend/index.html` — Apple PWA meta tags + manifest link.
- `frontend/public/manifest.webmanifest`, `frontend/public/sw.js` — PWA manifest + service worker.
- `frontend/public/icon-180.png|icon-192.png|icon-512.png` — PWA icons.
- `frontend/src/main.jsx` — register service worker in secure context.
- `scripts/make_icon.py` — also emit 180/192/512 PWA icons.
- `electron/main.js` — pass `GARMIN_DASH_STATIC`; `loadURL` with retry.
- `package.json` — `frontend/dist` as `extraResources`; drop it from asar `files`.
- `README.md` — phone‑access setup (Tailscale, LAN, Safari install, optional Tailscale Serve HTTPS).

---

### Task 1: Settings — `phone_access` and `access_pin`

**Files:**
- Modify: `backend/settings.py`
- Test: `backend/tests/test_phone_access.py`

**Interfaces:**
- Produces: `DEFAULTS` gains `"phone_access": False`, `"access_pin": ""`; `load_settings`/`save_settings` validate them (bool / str).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_phone_access.py`:
```python
import backend.settings as st


def test_phone_access_and_pin_defaults(tmp_path):
    s = st.load_settings(tmp_path / "settings.json")
    assert s["phone_access"] is False
    assert s["access_pin"] == ""


def test_phone_access_coerced_to_bool_and_pin_to_str(tmp_path):
    p = tmp_path / "settings.json"
    saved = st.save_settings(p, {"phone_access": 1, "access_pin": 1234})
    assert saved["phone_access"] is True
    assert saved["access_pin"] == "1234"
    assert st.load_settings(p) == saved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_phone_access.py -q`
Expected: FAIL — `KeyError: 'phone_access'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/settings.py`, add to `DEFAULTS`:
```python
    "phone_access": False,        # bind to LAN/Tailscale so a phone can reach it
    "access_pin": "",             # required for any non-loopback API access
```
In `_validate`, before `return s`:
```python
    s["phone_access"] = bool(s["phone_access"])
    s["access_pin"] = str(s.get("access_pin") or "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_phone_access.py backend/tests/test_settings.py -q`
Expected: PASS (including the existing `test_defaults_when_no_file`).

- [ ] **Step 5: Commit**

```bash
git add backend/settings.py backend/tests/test_phone_access.py
git commit -m "feat: phone_access + access_pin settings"
```

---

### Task 2: Access PIN gate (before_request)

**Files:**
- Modify: `backend/api.py` (inside `create_app`, after `_local_cors`)
- Test: `backend/tests/test_phone_access.py`

**Interfaces:**
- Consumes: `access_pin` from settings (Task 1).
- Produces: non‑loopback `/api/*` requests get `401 {"error":"pin_required"}` unless header `X-Access-Pin` matches a non‑empty configured PIN. Loopback and non‑`/api` paths pass.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_phone_access.py`:
```python
from unittest.mock import MagicMock
import backend.db as db
import backend.settings as st
from backend.api import create_app


def _client(tmp_path, pin=""):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    st.save_settings(tmp_path / "settings.json", {"phone_access": True, "access_pin": pin})
    app = create_app(p, client_factory=lambda: MagicMock(), tokenstore=tmp_path / "garth")
    return app.test_client()


def test_loopback_bypasses_pin(tmp_path):
    c = _client(tmp_path, pin="1234")
    assert c.get("/api/sync-status").status_code == 200  # default REMOTE_ADDR is 127.0.0.1


def test_remote_requires_valid_pin(tmp_path):
    c = _client(tmp_path, pin="1234")
    remote = {"REMOTE_ADDR": "192.168.1.20"}
    assert c.get("/api/sync-status", environ_base=remote).status_code == 401
    ok = c.get("/api/sync-status", environ_base=remote, headers={"X-Access-Pin": "1234"})
    assert ok.status_code == 200


def test_remote_denied_when_no_pin_configured(tmp_path):
    c = _client(tmp_path, pin="")
    r = c.get("/api/sync-status", environ_base={"REMOTE_ADDR": "10.0.0.9"},
              headers={"X-Access-Pin": ""})
    assert r.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_phone_access.py -q`
Expected: FAIL — remote requests return 200 (no gate yet).

- [ ] **Step 3: Write minimal implementation**

In `backend/api.py`, add `import hmac` at top. Inside `create_app`, right after the `_local_cors` `after_request` function:
```python
    @app.before_request
    def _gate_non_loopback():
        from flask import request
        if not request.path.startswith("/api/"):
            return None  # static/app shell loads freely so the phone can render
        if request.remote_addr in ("127.0.0.1", "::1", None):
            return None  # the desktop app (loopback) needs no PIN
        from backend import settings as st
        pin = st.load_settings(Path(db_path).parent / "settings.json")["access_pin"]
        supplied = request.headers.get("X-Access-Pin", "")
        if not pin or not hmac.compare_digest(supplied, pin):
            return jsonify({"error": "pin_required"}), 401
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_phone_access.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api.py backend/tests/test_phone_access.py
git commit -m "feat: PIN gate for non-loopback API access"
```

---

### Task 3: Flask serves the SPA (static + SPA fallback)

**Files:**
- Modify: `backend/config.py` (add `resolve_static_dir`), `backend/api.py` (routes + `create_app` param)
- Test: `backend/tests/test_phone_access.py`

**Interfaces:**
- Produces: `create_app(..., static_dir=None)`; `GET /` returns `index.html`; `GET /<file>` serves it if present else falls back to `index.html`; `/api/*` unaffected. `config.resolve_static_dir()` → `$GARMIN_DASH_STATIC` or `<repo>/frontend/dist`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_phone_access.py`:
```python
def _client_static(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>APP-SHELL</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    app = create_app(p, client_factory=lambda: MagicMock(),
                     tokenstore=tmp_path / "garth", static_dir=str(dist))
    return app.test_client()


def test_serves_index_and_assets(tmp_path):
    c = _client_static(tmp_path)
    assert b"APP-SHELL" in c.get("/").data
    assert c.get("/assets/app.js").status_code == 200


def test_spa_fallback_serves_index_for_unknown_path(tmp_path):
    c = _client_static(tmp_path)
    r = c.get("/sleep")
    assert r.status_code == 200 and b"APP-SHELL" in r.data


def test_api_route_not_shadowed_by_static(tmp_path):
    c = _client_static(tmp_path)
    assert c.get("/api/sync-status").get_json() is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_phone_access.py -q`
Expected: FAIL — `create_app() got an unexpected keyword argument 'static_dir'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/config.py` add:
```python
def resolve_static_dir():
    import os
    env = os.environ.get("GARMIN_DASH_STATIC")
    if env:
        return env
    return str(Path(__file__).resolve().parent.parent / "frontend" / "dist")
```
In `backend/api.py`: add `import os` and `from flask import send_from_directory, abort` to the imports. Change the signature:
```python
def create_app(db_path=cfg.DB_PATH, client_factory=None,
               tokenstore=cfg.TOKENSTORE_DIR, auth_client_factory=None,
               static_dir=None):
    app = Flask(__name__, static_folder=None)
    static_dir = static_dir or cfg.resolve_static_dir()
```
At the **end** of `create_app`, just before `return app`, register the catch‑all (API routes are already registered, so they win):
```python
    @app.get("/")
    def _spa_index():
        return send_from_directory(static_dir, "index.html")

    @app.get("/<path:filename>")
    def _spa_static(filename):
        if filename.startswith("api/"):
            abort(404)
        full = os.path.join(static_dir, filename)
        if os.path.isfile(full):
            return send_from_directory(static_dir, filename)
        return send_from_directory(static_dir, "index.html")  # SPA fallback
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_phone_access.py backend/tests/test_phase6_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api.py backend/config.py backend/tests/test_phone_access.py
git commit -m "feat: Flask serves the SPA with API-safe SPA fallback"
```

---

### Task 4: Bind host from settings + `main()` uses it

**Files:**
- Modify: `backend/api.py` (`resolve_host` helper + `main()`)
- Test: `backend/tests/test_phone_access.py`

**Interfaces:**
- Produces: `api.resolve_host(settings)` → `$GARMIN_DASH_HOST` if set, else `"0.0.0.0"` when `phone_access` else `"127.0.0.1"`. `main()` binds with it.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_phone_access.py`:
```python
import backend.api as api


def test_resolve_host_localhost_by_default(monkeypatch):
    monkeypatch.delenv("GARMIN_DASH_HOST", raising=False)
    assert api.resolve_host({"phone_access": False}) == "127.0.0.1"


def test_resolve_host_all_interfaces_when_enabled(monkeypatch):
    monkeypatch.delenv("GARMIN_DASH_HOST", raising=False)
    assert api.resolve_host({"phone_access": True}) == "0.0.0.0"


def test_resolve_host_env_override(monkeypatch):
    monkeypatch.setenv("GARMIN_DASH_HOST", "100.64.0.7")
    assert api.resolve_host({"phone_access": True}) == "100.64.0.7"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_phone_access.py -q`
Expected: FAIL — `AttributeError: module 'backend.api' has no attribute 'resolve_host'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/api.py`, add near the top (after imports):
```python
def resolve_host(settings):
    """Which interface to bind: env override, else all-interfaces when phone
    access is on, else loopback only."""
    env = os.environ.get("GARMIN_DASH_HOST")
    if env:
        return env
    return "0.0.0.0" if settings.get("phone_access") else "127.0.0.1"
```
In `main()`, replace `app.run(host="127.0.0.1", port=5057)` with:
```python
    from backend import settings as st
    host = resolve_host(st.load_settings(Path(cfg.DB_PATH).parent / "settings.json"))
    app.run(host=host, port=5057)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest backend -q`
Expected: PASS — all tests (was 110, now +new phone-access tests).

- [ ] **Step 5: Commit**

```bash
git add backend/api.py backend/tests/test_phone_access.py
git commit -m "feat: bind host from phone_access setting"
```

---

### Task 5: Same-origin frontend + PIN screen + Electron loadURL + dev proxy

**Files:**
- Modify: `frontend/src/api.js`, `frontend/src/App.jsx`, `frontend/vite.config.js`, `electron/main.js`
- Create: `frontend/src/PinGate.jsx`

**Interfaces:**
- Consumes: backend PIN gate (401) and same‑origin serving (Tasks 2–3).
- Produces: `api.js` calls are same‑origin and carry `X-Access-Pin` from `localStorage.accessPin`; on 401 the app shows `PinGate`, which stores the PIN and reloads.

- [ ] **Step 1: Same-origin + PIN header in `api.js`**

Replace the top of `frontend/src/api.js`:
```javascript
const BASE = ""; // same-origin: Flask serves both the app and the API
async function j(path, opts) {
  const pin = localStorage.getItem("accessPin") || "";
  const headers = { ...(opts && opts.headers), ...(pin ? { "X-Access-Pin": pin } : {}) };
  const r = await fetch(BASE + path, { ...opts, headers });
  if (r.status === 401) {
    window.dispatchEvent(new Event("pin-required"));
    throw new Error("pin_required");
  }
  if (!r.ok) throw new Error("api " + r.status);
  return r.json();
}
```
(Leave `exportUrl` returning a relative `/api/export/...`.)

- [ ] **Step 2: Create the PIN screen** `frontend/src/PinGate.jsx`:
```javascript
import React, { useState } from "react";

export default function PinGate() {
  const [pin, setPin] = useState("");
  const submit = (e) => {
    e.preventDefault();
    localStorage.setItem("accessPin", pin.trim());
    window.location.reload();
  };
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-lg font-semibold text-neutral-100">Enter access PIN</h1>
      <p className="max-w-xs text-sm text-neutral-400">
        This dashboard is protected. Enter the PIN you set on your PC (Settings →
        Enable phone access).
      </p>
      <form onSubmit={submit} className="flex gap-2">
        <input autoFocus type="password" inputMode="numeric" value={pin}
          onChange={(e) => setPin(e.target.value)}
          className="rounded-lg border border-line/10 bg-neutral-900 px-3 py-2 text-neutral-100" />
        <button className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-neutral-50 hover:bg-emerald-500">
          Unlock
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Show `PinGate` on 401 in `App.jsx`**

Add `import PinGate from "./PinGate.jsx";`. Add state + listener near the other hooks:
```javascript
  const [pinRequired, setPinRequired] = useState(false);
  useEffect(() => {
    const h = () => setPinRequired(true);
    window.addEventListener("pin-required", h);
    return () => window.removeEventListener("pin-required", h);
  }, []);
```
At the top of the returned render (before `if (authed === false)`):
```javascript
  if (pinRequired) return <PinGate />;
```

- [ ] **Step 4: Dev proxy** — replace `server: { port: 5173 }` in `frontend/vite.config.js`:
```javascript
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:5057" } },
```

- [ ] **Step 5: Electron loads via localhost URL** — in `electron/main.js` `createWindow`, replace `win.loadFile(path.join(ROOT, "frontend", "dist", "index.html"));` with a retrying load:
```javascript
  const load = () => win.loadURL("http://127.0.0.1:5057/").catch(() => setTimeout(load, 400));
  load();
```

- [ ] **Step 6: Verify (preview)**

Build the frontend: `npm --prefix frontend run build`. Start the backend: `.venv/Scripts/python -m backend.api`. Start the preview (Vite) via `preview_start` (config already exists) and confirm the dashboard loads through the dev proxy with no console errors (`preview_console_logs level=error`), and that `preview_screenshot` shows the normal dashboard. (The PIN screen only triggers from a non‑loopback address; it's verified on‑device in Task 8.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api.js frontend/src/PinGate.jsx frontend/src/App.jsx frontend/vite.config.js electron/main.js
git commit -m "feat: same-origin API + PIN screen; Electron loads via localhost URL"
```

---

### Task 6: PWA — icons, manifest, Apple tags, service worker

**Files:**
- Modify: `scripts/make_icon.py`, `frontend/index.html`, `frontend/src/main.jsx`
- Create: `frontend/public/manifest.webmanifest`, `frontend/public/sw.js`, `frontend/public/icon-180.png`, `frontend/public/icon-192.png`, `frontend/public/icon-512.png`

**Interfaces:**
- Produces: installable PWA; iOS home‑screen works via Apple tags without a SW; SW registers only in a secure context.

- [ ] **Step 1: Emit PWA icons** — at the end of `scripts/make_icon.py` `build()`, after saving `OUT`, add:
```python
    base = icon.resize((512, 512), Image.LANCZOS)
    pub = OUT.parent.parent / "frontend" / "public"
    pub.mkdir(parents=True, exist_ok=True)
    for size in (180, 192, 512):
        base.resize((size, size), Image.LANCZOS).save(pub / f"icon-{size}.png")
        print(f"wrote {pub / f'icon-{size}.png'}")
```
Run: `.venv/Scripts/python scripts/make_icon.py`
Expected: writes `build/icon.png` and `frontend/public/icon-{180,192,512}.png`.

- [ ] **Step 2: Manifest** — create `frontend/public/manifest.webmanifest`:
```json
{
  "name": "Recovery Dashboard",
  "short_name": "Recovery",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#09090b",
  "theme_color": "#09090b",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

- [ ] **Step 3: Apple tags + manifest link** — in `frontend/index.html`, inside `<head>`:
```html
    <link rel="manifest" href="/manifest.webmanifest" />
    <meta name="theme-color" content="#09090b" />
    <link rel="apple-touch-icon" href="/icon-180.png" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
    <meta name="apple-mobile-web-app-title" content="Recovery" />
```

- [ ] **Step 4: Service worker** — create `frontend/public/sw.js`:
```javascript
// App-shell cache. Live API data is always fetched from the network.
const CACHE = "recovery-shell-v1";
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(["/", "/index.html"])));
  self.skipWaiting();
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) =>
    Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/")) return; // never cache API
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
```

- [ ] **Step 5: Register SW only in a secure context** — at the end of `frontend/src/main.jsx`:
```javascript
// iOS blocks service workers over plain http; register only where supported.
if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
```

- [ ] **Step 6: Verify (build + preview)**

Run `npm --prefix frontend run build` and confirm `dist/manifest.webmanifest`, `dist/sw.js`, and `dist/icon-192.png` exist (Vite copies `public/`). Start backend + preview; `preview_eval` `document.querySelector('link[rel=manifest]').href` returns the manifest URL, and `navigator.serviceWorker.controller` is set after a reload (localhost is a secure context). No console errors.

- [ ] **Step 7: Commit**

```bash
git add scripts/make_icon.py frontend/index.html frontend/src/main.jsx frontend/public
git commit -m "feat: PWA manifest, Apple tags, icons, secure-context service worker"
```

---

### Task 7: Packaging — frozen backend serves the SPA

**Files:**
- Modify: `electron/main.js` (pass `GARMIN_DASH_STATIC`), `package.json` (`extraResources` + `files`)

**Interfaces:**
- Consumes: `config.resolve_static_dir()` (reads `GARMIN_DASH_STATIC`) from Task 3.
- Produces: the packaged app's backend serves `frontend/dist` from an unpacked resource; Electron loads `http://127.0.0.1:5057/`.

- [ ] **Step 1: Pass the static path to the backend** — in `electron/main.js` `startBackend`, add to the spawn `env`:
```javascript
      GARMIN_DASH_DATA_DIR: app.getPath("userData"),
      GARMIN_DASH_STATIC: app.isPackaged
        ? path.join(process.resourcesPath, "frontend")
        : path.join(ROOT, "frontend", "dist"),
```

- [ ] **Step 2: Ship `frontend/dist` as a resource** — in `package.json` `build`, add to `extraResources`:
```json
      { "from": "frontend/dist", "to": "frontend" }
```
and remove `"frontend/dist/**"` from the `files` array (Electron no longer loads it directly; the backend serves it).

- [ ] **Step 3: Build the packaged app**

Run: `npm run dist:win`
Expected: EXIT 0; `release/GarminRecoveryDashboard-Setup-3.2.0.exe` produced (note: bump version later when releasing).

- [ ] **Step 4: Smoke-test the packaged app**

Install/run the packaged app (or run `release/win-unpacked/Garmin Recovery Dashboard.exe`). Confirm the window loads the dashboard (served from `http://127.0.0.1:5057/`) and the backend logs show it bound. Confirm `curl http://127.0.0.1:5057/` returns the SPA HTML.

- [ ] **Step 5: Commit**

```bash
git add electron/main.js package.json
git commit -m "feat: package frontend as a resource; backend serves it in the frozen app"
```

---

### Task 8: Responsive pass + docs + on-device verification

**Files:**
- Modify: whichever components need mobile fixes (likely `frontend/src/App.jsx` header, `frontend/src/detail/DetailPanel.jsx`, gauges), `README.md`

**Interfaces:** none new — polish + documentation.

- [ ] **Step 1: Find mobile issues**

Start backend + preview. `preview_resize preset=mobile` (375×812). `preview_screenshot` each tab. Note overflow/cramping in: header actions, the detail panel width, gauge sizing, the date navigator, the Leaflet map height.

- [ ] **Step 2: Fix issues (one commit)**

Apply Tailwind fixes (examples — adjust to what the screenshots show): ensure the header wraps (`flex-wrap` already present — verify), make `DetailPanel` full‑width on mobile (`w-full sm:max-w-md`), reduce gauge `size` on small screens if clipped, constrain the map height. Re‑screenshot at 375px and at desktop width to confirm both look right and `preview_console_logs level=error` is clean.

- [ ] **Step 3: Commit the responsive fixes**

```bash
git add frontend/src
git commit -m "style: responsive fixes for phone widths"
```

- [ ] **Step 4: README — phone access section**

Add a "Use it on your phone" section to `README.md`:
```markdown
## Use it on your phone (LAN + Tailscale)

1. **Enable it:** in the app, Settings → **Enable phone access** and set a **PIN**,
   then relaunch (the server now binds to your network).
2. **On the same Wi‑Fi:** open Safari on your iPhone → `http://<your-pc-ip>:5057`.
3. **From anywhere:** install **Tailscale** on your PC and iPhone (same account),
   then open `http://<your-pc-name>:5057` (Tailscale MagicDNS).
4. Enter the PIN once, then Share → **Add to Home Screen** for a full‑screen app.

Only your own PC needs no PIN; every phone/network request needs it. Binding to the
network exposes port 5057 on your LAN — the PIN protects it; Tailscale‑only use is
most private. *(Optional: `tailscale serve https / http://127.0.0.1:5057` gives an
`https://<name>.ts.net` address — a secure context that also enables the offline
service worker.)*
```

- [ ] **Step 5: On-device verification**

With `phone_access` on + a PIN set and the backend bound (`0.0.0.0`), open the URL from the iPhone (LAN and/or Tailscale): confirm the **PIN screen** appears, the PIN unlocks the dashboard, the layout is good, and **Add to Home Screen** launches full‑screen. Confirm the desktop app still loads with no PIN.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: phone access (LAN + Tailscale, Safari install)"
```

---

## Self-Review

**Spec coverage:** Flask‑serves‑SPA (T3), same‑origin + Electron loadURL + dev proxy (T5), bind host + phone_access (T1/T4), PIN gate + PIN UI (T2/T5), PWA manifest/Apple‑tags/SW/icons (T6), packaging so the frozen backend serves the SPA (T7), responsive pass + Tailscale/LAN/Safari docs + optional Tailscale Serve (T8). All spec sections map to a task.

**Placeholders:** none — every code step shows the code; every test step shows the assertion and the run command/expected result.

**Type/name consistency:** `resolve_host(settings)`, `resolve_static_dir()`, `create_app(..., static_dir=None)`, the `pin-required` window event, and `localStorage.accessPin` are used identically across the tasks that define and consume them. Settings keys `phone_access` / `access_pin` match between backend and the README/UI copy.

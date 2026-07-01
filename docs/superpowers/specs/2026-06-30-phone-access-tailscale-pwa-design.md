# Phone access — LAN + Tailscale, PWA-installable

Date: 2026-06-30
Status: Approved (design)

## Goal

Let the owner open their existing dashboard on their **phone** — on home Wi-Fi
(LAN) and from anywhere via **Tailscale** — installable to the home screen as a
PWA. Data stays on the PC (no cloud). This is Stage 1; a multi-user cloud site
remains a separate future project.

## Agreed decisions

- Reach the phone via **both LAN and Tailscale** (bind to all interfaces when
  enabled).
- A required **access PIN** gates all non-loopback API access (essential now that
  LAN — with other people's devices — is allowed).
- Make it an installable **PWA**; do a **responsive pass** for phone widths.
- Single-user, local-first preserved. No accounts, no cloud hosting.

## Architecture

Today: Electron loads the frontend from `file://`, and Flask serves only `/api/*`
bound to `127.0.0.1`. The frontend hardcodes `http://127.0.0.1:5057`. None of that
is reachable from a phone. Changes:

1. **Flask serves the SPA.** Add static routes so `GET /` returns the built
   `frontend/dist/index.html` and `/assets/*` etc. serve the bundle; unknown
   non-`/api` paths fall back to `index.html` (SPA routing). The API stays under
   `/api/*`.
   - **Packaging:** the frozen backend must locate the built frontend. electron-
     builder places `frontend/dist` as an `extraResource`; `electron/main.js`
     passes its path to the backend via an env var (`GARMIN_DASH_STATIC`), mirroring
     `GARMIN_DASH_DATA_DIR`. In dev, the backend serves `frontend/dist` if built, and
     Vite's dev server proxies `/api` → `127.0.0.1:5057` (new `server.proxy` config)
     so same-origin paths work in dev too.

2. **Same-origin frontend.** `api.js` `BASE` changes from `http://127.0.0.1:5057`
   to `""` (relative). Electron loads `http://127.0.0.1:5057/` (not `file://`) once
   the backend is up (retry `loadURL` until it binds). Desktop and phone then use an
   identical origin/path. The `_local_cors` header can be dropped (same-origin).

3. **Configurable bind host.** New setting `phone_access` (bool, default false).
   When true, the server binds `0.0.0.0` (LAN + Tailscale interfaces); when false,
   `127.0.0.1` (today's behavior). Applied at startup; toggling prompts a restart.
   Env override `GARMIN_DASH_HOST` for advanced use.

4. **Reachability.** Tailscale on PC + phone (same account) gives a private
   encrypted path from anywhere with no public exposure/port-forwarding; LAN works
   on the same Wi-Fi. Both hit the same `:5057`.

## Access PIN (security)

- New setting `access_pin` (string; empty = phone access refused for safety).
- Flask `before_request`: requests from **loopback** (`127.0.0.1`/`::1`) pass
  freely (the desktop app needs nothing). For any other remote address, `/api/*`
  requires header `X-Access-Pin` equal to `access_pin`, else `401`. Static assets
  (the app shell) load without the PIN so the phone can render the PIN prompt.
- Frontend: on a `401` from the API (i.e., non-loopback without a valid PIN), show a
  **PIN entry screen**; store the PIN in `localStorage`; send it as `X-Access-Pin`
  on every request. Loopback (Electron) never sees the prompt.
- Constant-time PIN comparison; PIN never logged (extend the existing redaction).

## PWA

- `manifest.webmanifest` (name, `display: standalone`, theme/background from the
  dark palette, `start_url: "/"`, icons) served by Flask and linked from
  `index.html`.
- Icons: generate `icon-192.png` and `icon-512.png` from `build/icon.png` (extend
  `scripts/make_icon.py` to also emit PWA sizes).
- Minimal **service worker** caching the app shell (HTML/JS/CSS) for installability
  and fast loads; API responses are always network (live data). Registered from
  `main.jsx`.

## Responsive pass

Test at 375px and fix: header (wrap/spacing), tab nav (already
`overflow-x-auto`), gauges (size down on narrow screens), the slide-in DetailPanel
(full-width on mobile), the date navigator, and the Leaflet map height. Verify in
the preview at mobile width + the existing desktop layout is unchanged.

## How the owner uses it

1. Install Tailscale on PC + phone (same login).
2. In the app: **Settings → Enable phone access**, set a **PIN**, relaunch.
3. Phone (home Wi-Fi): `http://<pc-lan-ip>:5057`; away: `http://<pc-name>:5057`
   (Tailscale MagicDNS). Enter the PIN once → **Add to Home Screen**.

## Out of scope (YAGNI)

Cloud hosting, accounts/signups, friend features, offline data sync, HTTPS certs
(Tailscale/LAN are already private; the PIN gates access).

## Testing

- Backend: PIN gate (loopback bypass; non-loopback 401 without/with PIN); static
  serving + SPA fallback; `phone_access`/`access_pin` settings validation. Existing
  110 tests stay green.
- Frontend/manual: verify phone flow in the preview (mobile viewport, PIN screen,
  install); verify the desktop Electron app still loads via localhost and needs no
  PIN.

## Risks

- Binding `0.0.0.0` exposes `:5057` on the LAN — mitigated by the required PIN and
  (recommended) Tailscale-only use. Document the trade-off.
- Packaged backend serving static files is a new path — validate the frozen build,
  not just dev.
- Electron `loadURL` races the backend bind — retry until ready.

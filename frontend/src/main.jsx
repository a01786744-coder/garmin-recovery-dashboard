import React from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";

// Apply the saved theme before first paint to avoid a flash of the wrong theme.
// localStorage is a fast mirror of the settings.json `theme` (the source of
// truth, loaded from the backend shortly after).
const saved = localStorage.getItem("theme");
document.documentElement.dataset.theme = saved === "light" ? "light" : "dark";

createRoot(document.getElementById("root")).render(<App />);

// iOS blocks service workers over plain http; register only in a secure context
// (localhost or HTTPS, e.g. Tailscale Serve). On iOS-over-http this no-ops and the
// home-screen install still works via the apple-mobile-web-app meta tags.
if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

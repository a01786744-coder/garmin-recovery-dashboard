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

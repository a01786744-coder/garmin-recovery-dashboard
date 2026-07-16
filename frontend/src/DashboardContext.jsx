import React, { createContext, useContext } from "react";

// Everything a widget needs to render, provided once by App so widgets work
// identically on a built-in tab or a user-composed custom tab.
const DashboardCtx = createContext(null);

export function DashboardProvider({ value, children }) {
  return <DashboardCtx.Provider value={value}>{children}</DashboardCtx.Provider>;
}

export function useDashboard() {
  return useContext(DashboardCtx) || {};
}

import React from "react";

export default function Badge({ children, color = "#52525b" }) {
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{ background: color + "22", color, border: `1px solid ${color}44` }}
    >
      {children}
    </span>
  );
}

import React from "react";

export default function NoData({ label = "No data", className = "", height }) {
  return (
    <div
      className={"flex items-center justify-center text-neutral-600 text-sm " + className}
      style={height ? { height } : undefined}
    >
      {label}
    </div>
  );
}

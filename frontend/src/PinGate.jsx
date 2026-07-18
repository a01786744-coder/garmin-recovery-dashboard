import React, { useState } from "react";

// Shown when the API returns 401 (a phone/network request without a valid PIN).
// The desktop app talks over loopback and never hits this.
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
        This dashboard is protected. Enter the PIN you set on your PC
        (Settings → Enable phone access).
      </p>
      <form onSubmit={submit} className="flex gap-2">
        <input autoFocus type="password" inputMode="numeric" value={pin}
          onChange={(e) => setPin(e.target.value)}
          className="rounded-lg border border-line/10 bg-neutral-900 px-3 py-2 text-neutral-100" />
        <button className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-neutral-50 hover:bg-accent/90">
          Unlock
        </button>
      </form>
    </div>
  );
}

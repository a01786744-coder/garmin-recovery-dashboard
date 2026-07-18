import React, { useState } from "react";
import { motion } from "framer-motion";
import { postLogin, postMfa } from "./api.js";

const ERRORS = {
  missing_credentials: "Enter your email and password.",
  authentication_failed: "Incorrect email or password.",
  rate_limited: "Garmin is rate-limiting login attempts. Wait a few minutes and try again.",
  connection_error: "Couldn't reach Garmin Connect. Check your internet connection.",
  mfa_failed: "That code didn't work. Try the latest code.",
  network: "Couldn't reach the local service. Is the app still starting?",
};

export default function Login({ onSuccess, notice }) {
  const [stage, setStage] = useState("login"); // "login" | "mfa"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const submitLogin = async (e) => {
    e.preventDefault();
    if (!email || !password) return setError(ERRORS.missing_credentials);
    setBusy(true);
    setError(null);
    try {
      const r = await postLogin(email, password);
      if (r.status === "ok") onSuccess();
      else if (r.status === "mfa_required") setStage("mfa");
      else setError(ERRORS[r.message] || "Login failed.");
    } catch (err) {
      setError(ERRORS.network);
    } finally {
      setBusy(false);
      setPassword(""); // don't keep the password in component state longer than needed
    }
  };

  const submitMfa = async (e) => {
    e.preventDefault();
    if (!code) return;
    setBusy(true);
    setError(null);
    try {
      const r = await postMfa(code);
      if (r.status === "ok") onSuccess();
      else setError(ERRORS[r.message] || "Verification failed.");
    } catch (err) {
      setError(ERRORS.network);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="w-full max-w-sm rounded-2xl border border-line/5 bg-neutral-900/70 p-6 shadow-xl shadow-black/30 backdrop-blur"
      >
        <h1 className="text-lg font-bold text-neutral-50">Recovery Dashboard</h1>
        {notice && (
          <p className="mt-2 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
            {notice}
          </p>
        )}
        <p className="mb-5 text-xs text-neutral-500">
          Sign in with your Garmin Connect account. Your password is sent once to
          Garmin and never stored — only a login token is kept on this device.
        </p>

        {stage === "login" ? (
          <form onSubmit={submitLogin} className="space-y-3">
            <input
              type="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="Garmin email"
              className="w-full rounded-lg border border-line/10 bg-neutral-950/60 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-accent/60"
            />
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="w-full rounded-lg border border-line/10 bg-neutral-950/60 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-accent/60"
            />
            <Submit busy={busy} label="Sign in" />
          </form>
        ) : (
          <form onSubmit={submitMfa} className="space-y-3">
            <p className="text-sm text-neutral-300">
              Enter the verification code Garmin just sent you.
            </p>
            <input
              type="text" inputMode="numeric" autoFocus value={code}
              onChange={(e) => setCode(e.target.value.trim())}
              placeholder="6-digit code"
              className="w-full rounded-lg border border-line/10 bg-neutral-950/60 px-3 py-2 text-center text-lg tracking-widest text-neutral-100 outline-none focus:border-accent/60"
            />
            <Submit busy={busy} label="Verify" />
            <button type="button" onClick={() => { setStage("login"); setCode(""); setError(null); }}
              className="w-full text-center text-xs text-neutral-500 hover:text-neutral-300">
              Back
            </button>
          </form>
        )}

        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

        <p className="mt-5 text-[10px] leading-relaxed text-neutral-600">
          Unofficial — not affiliated with Garmin. For personal insight only; not medical advice.
        </p>
      </motion.div>
    </div>
  );
}

function Submit({ busy, label }) {
  return (
    <motion.button
      whileTap={{ scale: 0.98 }} type="submit" disabled={busy}
      className="w-full rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-neutral-50 hover:bg-accent/90 disabled:opacity-50"
    >
      {busy ? "Working…" : label}
    </motion.button>
  );
}

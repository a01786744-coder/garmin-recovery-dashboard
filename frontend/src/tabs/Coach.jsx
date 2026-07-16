import React, { useEffect, useRef, useState } from "react";
import Card from "../components/ui/Card.jsx";
import SectionTitle from "../components/ui/SectionTitle.jsx";
import WorkoutCard from "../components/WorkoutCard.jsx";
import CoachText, { Highlights } from "../components/CoachText.jsx";
import {
  getCoachStatus, getCoachBrief, getCoachChat, postCoachChat, clearCoachChat,
  getCoachWorkouts, deleteCoachWorkout,
} from "../api.js";
import { fmtDay } from "../format.js";

function Setup() {
  return (
    <Card>
      <SectionTitle sub="Personal AI coach powered by Claude">Coach setup</SectionTitle>
      <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-neutral-300">
        <li>Create an API key at <b>console.anthropic.com</b> → API keys.</li>
        <li>Open <b>Settings → AI Coach</b> here, paste the key and enable the coach.</li>
        <li>Come back to this tab — your first daily brief will be ready.</li>
      </ol>
      <p className="mt-3 text-xs text-neutral-500">
        Privacy: the coach sends your recent metrics, activities and journal to
        Anthropic's API to generate advice — nothing else, and never your Garmin
        credentials. The key is stored only on this machine. Typical cost is
        $1–3/month. Everything else in the app stays fully local.
      </p>
    </Card>
  );
}

function Brief() {
  const [brief, setBrief] = useState(null);
  const [loading, setLoading] = useState(true);
  const load = async (force = false) => {
    setLoading(true);
    try { setBrief(await getCoachBrief(force)); } catch { setBrief({ error: "network" }); }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  return (
    <Card>
      <div className="flex items-center justify-between">
        <SectionTitle sub="Generated from your latest data">Today's brief</SectionTitle>
        <button onClick={() => load(true)} disabled={loading}
          className="rounded-lg px-2.5 py-1 text-xs text-neutral-400 hover:text-neutral-100 disabled:opacity-50">
          ↻ Regenerate
        </button>
      </div>
      {loading ? (
        <div className="mt-2 space-y-2">
          <div className="h-4 w-3/4 animate-pulse rounded bg-neutral-800" />
          <div className="h-4 w-full animate-pulse rounded bg-neutral-800" />
          <div className="h-4 w-2/3 animate-pulse rounded bg-neutral-800" />
        </div>
      ) : brief?.error ? (
        <p className="mt-2 text-sm text-red-400">
          Couldn't reach the coach ({brief.error}). Check your API key in Settings.
        </p>
      ) : (
        <div className="mt-2">
          <Highlights items={brief?.highlights} />
          <CoachText text={brief?.text} />
          {brief?.workout && (
            <div className="mt-3"><WorkoutCard workout={brief.workout} /></div>
          )}
        </div>
      )}
    </Card>
  );
}

function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    getCoachChat().then((r) => setMessages(r.messages || [])).catch(() => {});
  }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); },
    [messages, busy]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);
    try {
      const res = await postCoachChat(text);
      setMessages((m) => [...m, res.error
        ? { role: "assistant", content: `Something went wrong (${res.error}).` }
        : { role: "assistant", content: res.reply, workout: res.workout,
            highlights: res.highlights }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Network error — try again." }]);
    }
    setBusy(false);
  };

  const clear = async () => {
    await clearCoachChat().catch(() => {});
    setMessages([]);
  };

  return (
    <Card hover={false}>
      <div className="flex items-center justify-between">
        <SectionTitle sub="Ask about training, recovery, race prep — or request a workout">
          Ask your coach
        </SectionTitle>
        {messages.length > 0 && (
          <button onClick={clear}
            className="rounded-lg px-2.5 py-1 text-xs text-neutral-500 hover:text-neutral-200">
            Clear
          </button>
        )}
      </div>

      <div className="mt-2 max-h-[50vh] space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 && !busy && (
          <div className="flex flex-wrap gap-2 py-2">
            {["Should I run today?", "Design me an interval workout",
              "Why was my recovery low this week?", "Plan my week"].map((q) => (
              <button key={q} onClick={() => setInput(q)}
                className="rounded-full border border-line/10 px-3 py-1.5 text-xs text-neutral-400 hover:border-line/30 hover:text-neutral-200">
                {q}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
            <div className={m.role === "user"
              ? "max-w-[85%] rounded-2xl rounded-br-sm bg-emerald-500/15 px-3.5 py-2 text-sm text-neutral-100"
              : "max-w-[95%]"}>
              {m.role === "assistant" ? (
                <div className="rounded-2xl rounded-bl-sm bg-neutral-950/60 px-3.5 py-2.5">
                  <Highlights items={m.highlights} />
                  <CoachText text={m.content} />
                </div>
              ) : m.content}
              {m.workout && <div className="mt-2"><WorkoutCard workout={m.workout} /></div>}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex items-center gap-2 text-sm text-neutral-500">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-neutral-600 border-t-neutral-300" />
            Coach is thinking…
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="mt-3 flex gap-2">
        <input value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask your coach anything…"
          className="flex-1 rounded-xl border border-line/10 bg-neutral-950/60 px-3.5 py-2.5 text-sm text-neutral-100 placeholder:text-neutral-600 focus:border-emerald-500/40 focus:outline-none" />
        <button onClick={send} disabled={busy || !input.trim()}
          className="rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-40">
          Send
        </button>
      </div>
    </Card>
  );
}

function ScheduledWorkouts() {
  const [workouts, setWorkouts] = useState([]);
  const load = () => getCoachWorkouts().then((r) => setWorkouts(r.workouts || [])).catch(() => {});
  useEffect(() => { load(); }, []);
  const active = workouts.filter((w) => w.status !== "removed");
  if (!active.length) return null;

  return (
    <Card>
      <SectionTitle sub="Workouts this coach has pushed to your Garmin">On your watch</SectionTitle>
      <ul className="mt-1 divide-y divide-line/5">
        {active.map((w) => (
          <li key={w.id} className="flex items-center justify-between gap-2 py-2 text-sm">
            <div>
              <span className="text-neutral-100">{w.name}</span>
              <span className="ml-2 text-xs text-neutral-500">
                {w.date ? `scheduled ${fmtDay(w.date)}` : "uploaded"}
              </span>
            </div>
            <button
              onClick={async () => { await deleteCoachWorkout(w.id).catch(() => {}); load(); }}
              className="rounded-lg px-2.5 py-1 text-xs text-red-400/80 hover:bg-red-500/10 hover:text-red-300">
              Remove
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function Coach() {
  const [status, setStatus] = useState(null);
  useEffect(() => {
    getCoachStatus().then(setStatus).catch(() => setStatus({ configured: false }));
  }, []);

  if (!status) return <Card><div className="h-24 animate-pulse" /></Card>;
  if (!status.configured) return <Setup />;

  return (
    <div className="space-y-4">
      <Brief />
      <ScheduledWorkouts />
      <Chat />
    </div>
  );
}

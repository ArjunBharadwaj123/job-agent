"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

interface RunInfo {
  status: string | null;
  conclusion: string | null;
  run_started_at: string | null;
  html_url: string | null;
}
interface Status {
  scrape: RunInfo;
  email: RunInfo;
  etaSeconds: number;
}

function fmt(seconds: number) {
  if (seconds <= 0) return "wrapping up…";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `~${m}m ${s}s left` : `~${s}s left`;
}

export default function RefreshJobsButton() {
  const router = useRouter();
  const [running, setRunning] = useState(false);
  const [label, setLabel] = useState("");
  const [remaining, setRemaining] = useState<number | null>(null);
  const [runUrl, setRunUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const etaRef = useRef(540);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (tickRef.current) clearInterval(tickRef.current);
    pollRef.current = null;
    tickRef.current = null;
  }, []);

  const applyStatus = useCallback(
    (st: Status, justStarted = false): boolean => {
      etaRef.current = st.etaSeconds || 540;
      const scrape = st.scrape;
      setRunUrl(scrape.html_url);
      const active = scrape.status === "queued" || scrape.status === "in_progress";
      if (active) {
        setRunning(true);
        const started = scrape.run_started_at ? Date.parse(scrape.run_started_at) : Date.now();
        const elapsed = Math.floor((Date.now() - started) / 1000);
        setRemaining(Math.max(0, etaRef.current - elapsed));
        setLabel(scrape.status === "queued" ? "Queued…" : "Fetching new jobs");
        return true;
      }
      if (justStarted) {
        // Dispatched but the run row hasn't appeared yet.
        setRunning(true);
        setRemaining(etaRef.current);
        setLabel("Starting…");
        return true;
      }
      return false; // not active
    },
    []
  );

  const poll = useCallback(async () => {
    try {
      const st: Status = await (await fetch("/api/refresh", { cache: "no-store" })).json();
      const stillRunning = applyStatus(st);
      if (!stillRunning && running) {
        // Finished since last poll.
        stop();
        setRunning(false);
        setRemaining(null);
        setLabel(st.scrape.conclusion === "success" ? "Done — updated ✓" : "Finished");
        router.refresh();
        setTimeout(() => setLabel(""), 6000);
      }
    } catch {
      /* transient; keep polling */
    }
  }, [applyStatus, running, router, stop]);

  // Resume an in-progress run on mount.
  useEffect(() => {
    (async () => {
      try {
        const st: Status = await (await fetch("/api/refresh", { cache: "no-store" })).json();
        if (applyStatus(st)) startLoops();
      } catch {
        /* ignore */
      }
    })();
    return stop;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function startLoops() {
    stop();
    pollRef.current = setInterval(poll, 8000);
    tickRef.current = setInterval(() => setRemaining((r) => (r == null ? r : Math.max(0, r - 1))), 1000);
  }

  async function onClick() {
    if (running) return;
    setError(null);
    setLabel("Starting…");
    setRunning(true);
    setRemaining(etaRef.current);
    try {
      const res = await fetch("/api/refresh", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Couldn't start a refresh");
        setRunning(false);
        setLabel("");
        return;
      }
      // Give GitHub a moment to register the run, then poll.
      setTimeout(poll, 3000);
      startLoops();
    } catch {
      setError("Couldn't reach the refresh service");
      setRunning(false);
      setLabel("");
    }
  }

  return (
    <div className="flex items-center gap-3">
      {running && (
        <span className="text-sm text-zinc-500">
          {label}
          {remaining != null && ` — ${fmt(remaining)}`}
          {runUrl && (
            <>
              {" · "}
              <a href={runUrl} target="_blank" rel="noopener noreferrer" className="text-indigo-500 underline">
                view run
              </a>
            </>
          )}
        </span>
      )}
      {!running && label && <span className="text-sm text-emerald-500">{label}</span>}
      {error && <span className="text-sm text-rose-500">{error}</span>}
      <button
        onClick={onClick}
        disabled={running}
        className="flex items-center gap-1.5 rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
      >
        <span className={running ? "animate-spin" : ""}>↻</span>
        {running ? "Refreshing…" : "Refresh jobs"}
      </button>
    </div>
  );
}

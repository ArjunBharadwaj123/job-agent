"use client";

import { useEffect, useRef, useState } from "react";
import { STATUS_ORDER, STATUS_LABELS, STATUS_STYLES, type ApplicationStatus, type Job } from "@/lib/types";
import { localToday } from "@/lib/localDate";

// Inline status editor used in the jobs table: shows the coloured status badge
// as a trigger; clicking it opens a dropdown to change the status without
// opening the row's detail modal. The parent <td> stops click propagation so
// the row's onClick never fires from here.
export default function StatusSelect({ job, onChanged }: { job: Job; onChanged?: () => void }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<ApplicationStatus>(
    (job.application_status in STATUS_LABELS ? job.application_status : "not_applied") as ApplicationStatus
  );
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click or Escape.
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function pick(next: ApplicationStatus) {
    setOpen(false);
    if (next === status) return;
    const prev = status;
    setStatus(next); // optimistic
    setSaving(true);
    const res = await fetch(`/api/jobs/${job.job_id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ application_status: next, today: localToday() }),
    });
    setSaving(false);
    if (res.ok) {
      onChanged?.();
    } else {
      setStatus(prev); // revert on failure
    }
  }

  return (
    <div ref={ref} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={saving}
        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium transition hover:opacity-80 ${STATUS_STYLES[status]} ${saving ? "opacity-50" : ""}`}
      >
        {STATUS_LABELS[status]}
        <span aria-hidden className="text-[0.6rem] opacity-70">▾</span>
      </button>
      {open && (
        <div className="absolute left-0 top-full z-20 mt-1 min-w-[10rem] overflow-hidden rounded-lg border border-zinc-200 bg-white py-1 shadow-lg dark:border-zinc-700 dark:bg-zinc-900">
          {STATUS_ORDER.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => pick(s)}
              className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-zinc-100 dark:hover:bg-zinc-800 ${
                s === status ? "font-semibold" : ""
              }`}
            >
              <span className={`inline-flex rounded-full px-2 py-0.5 ${STATUS_STYLES[s]}`}>
                {STATUS_LABELS[s]}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

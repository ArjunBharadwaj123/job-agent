"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { STATUS_ORDER, STATUS_LABELS, PRIORITIES, type Job } from "@/lib/types";
import { localToday } from "@/lib/localDate";

export default function StatusControls({ job }: { job: Job }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [status, setStatus] = useState(job.application_status);
  const [priority, setPriority] = useState(job.priority ?? "");
  const [notes, setNotes] = useState(job.notes ?? "");
  const [saved, setSaved] = useState<string | null>(null);

  async function patch(body: Record<string, unknown>) {
    setSaved(null);
    const res = await fetch(`/api/jobs/${job.job_id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, today: localToday() }),
    });
    if (res.ok) {
      setSaved("Saved");
      startTransition(() => router.refresh());
    } else {
      setSaved("Error saving");
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
          Application status
        </label>
        <select
          value={status}
          onChange={(e) => {
            const v = e.target.value as typeof status;
            setStatus(v);
            patch({ application_status: v });
          }}
          className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          {STATUS_ORDER.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
          Priority
        </label>
        <select
          value={priority}
          onChange={(e) => {
            setPriority(e.target.value);
            patch({ priority: e.target.value || null });
          }}
          className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {p === "" ? "—" : p}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
          Notes
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={() => patch({ notes })}
          rows={4}
          placeholder="Your notes…"
          className="w-full resize-y rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
      </div>

      <div className="flex items-center gap-3 text-sm text-zinc-500">
        <button
          onClick={() => patch({ notes })}
          className="rounded-md bg-zinc-900 px-3 py-1.5 text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          Save notes
        </button>
        {isPending && <span>Refreshing…</span>}
        {saved && <span>{saved}</span>}
      </div>
    </div>
  );
}

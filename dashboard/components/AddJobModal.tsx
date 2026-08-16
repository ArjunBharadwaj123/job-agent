"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function AddJobModal() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const [fetching, setFetching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [existingId, setExistingId] = useState<string | null>(null);

  function reset() {
    setUrl(""); setTitle(""); setCompany(""); setLocation(""); setDescription("");
    setNote(null); setExistingId(null);
  }

  async function fetchDetails() {
    if (!url.trim()) return;
    setFetching(true); setNote(null);
    try {
      const res = await fetch("/api/jobs/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const d = await res.json();
      if (d.title) setTitle(d.title);
      if (d.company) setCompany(d.company);
      if (d.location) setLocation(d.location);
      if (d.description) setDescription(d.description);
      setNote(
        d.title || d.company
          ? "Read the posting ✓ — check the fields and save."
          : "Couldn't auto-read this page (some sites block it). Fill in the details."
      );
    } catch {
      setNote("Couldn't reach that URL. Fill in the details manually.");
    } finally {
      setFetching(false);
    }
  }

  async function save() {
    if (!title.trim() || !company.trim()) {
      setNote("Title and company are required.");
      return;
    }
    setSaving(true); setNote(null); setExistingId(null);
    const res = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, company, location, job_url: url, description }),
    });
    const d = await res.json();
    setSaving(false);
    if (!res.ok) {
      setNote(d.error || "Couldn't save.");
      return;
    }
    if (d.existing) {
      setExistingId(d.job_id);
      setNote("This job is already in your list.");
      return;
    }
    setOpen(false);
    reset();
    router.refresh();
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="rounded-lg bg-gradient-to-r from-indigo-500 to-violet-500 px-4 py-2 text-sm font-medium text-white hover:opacity-90"
      >
        + Add job
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 backdrop-blur-sm sm:p-8"
          onClick={() => setOpen(false)}
        >
          <div
            className="mt-6 w-full max-w-lg rounded-2xl border border-zinc-200 bg-white p-5 shadow-2xl dark:border-zinc-800 dark:bg-zinc-950"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Add a job</h2>
              <button onClick={() => setOpen(false)} className="text-xl leading-none text-zinc-400 hover:text-zinc-600">×</button>
            </div>

            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">Posting URL</label>
            <div className="flex gap-2">
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://…"
                className="flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              />
              <button
                onClick={fetchDetails}
                disabled={fetching || !url.trim()}
                className="whitespace-nowrap rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
              >
                {fetching ? "Reading…" : "Fetch details"}
              </button>
            </div>

            <div className="mt-4 space-y-3">
              <Field label="Title *" value={title} onChange={setTitle} />
              <Field label="Company *" value={company} onChange={setCompany} />
              <Field label="Location" value={location} onChange={setLocation} />
            </div>

            {note && (
              <p className="mt-3 text-sm text-zinc-500">
                {note}{" "}
                {existingId && (
                  <Link href={`/jobs/${existingId}`} className="text-indigo-600 underline dark:text-indigo-400">
                    Open it →
                  </Link>
                )}
              </p>
            )}

            <div className="mt-5 flex justify-end gap-2">
              <button onClick={() => setOpen(false)} className="rounded-lg px-4 py-2 text-sm text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800">
                Cancel
              </button>
              <button
                onClick={save}
                disabled={saving}
                className="rounded-lg bg-gradient-to-r from-indigo-500 to-violet-500 px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                {saving ? "Saving…" : "Add job"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
      />
    </label>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Resources, QA } from "@/lib/queries";

const BOOL_PREFS = [
  ["entry_level_only", "Entry-level / new-grad only"],
  ["us_only", "US locations only"],
  ["remote_allowed", "Allow remote"],
] as const;

function Section({ title, desc, children }: { title: string; desc?: string; children: React.ReactNode }) {
  return (
    <section className="mb-6 rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">{title}</h2>
      {desc && <p className="mt-1 text-xs text-zinc-400">{desc}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function SaveButton({ onClick, saving, saved }: { onClick: () => void; saving: boolean; saved: boolean }) {
  return (
    <div className="mt-4 flex items-center gap-3">
      <button
        onClick={onClick}
        disabled={saving}
        className="rounded-lg bg-gradient-to-r from-indigo-500 to-violet-500 px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save"}
      </button>
      {saved && <span className="text-sm text-emerald-500">Saved ✓</span>}
    </div>
  );
}

export default function SettingsForm({ initial }: { initial: Resources }) {
  const router = useRouter();
  const [resume, setResume] = useState(initial.resume);
  const [settings, setSettings] = useState<Record<string, string>>(initial.settings);
  const [answers, setAnswers] = useState<QA[]>(
    initial.answers.length ? initial.answers : DEFAULT_QUESTIONS.map((q) => ({ q, a: "" }))
  );
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [savedKey, setSavedKey] = useState<string | null>(null);

  async function save(key: string, patch: Record<string, unknown>) {
    setSavingKey(key);
    setSavedKey(null);
    const res = await fetch("/api/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    setSavingKey(null);
    if (res.ok) {
      setSavedKey(key);
      router.refresh();
      setTimeout(() => setSavedKey(null), 2500);
    }
  }

  const pref = (k: string) => settings[k] ?? "";
  const setPref = (k: string, v: string) => setSettings((s) => ({ ...s, [k]: v }));

  return (
    <div>
      {/* Resume */}
      <Section title="Resume" desc="Plain text. Used to score how well each job matches you.">
        <textarea
          value={resume}
          onChange={(e) => setResume(e.target.value)}
          rows={12}
          placeholder="Paste your resume text here…"
          className="w-full resize-y rounded-lg border border-zinc-300 bg-white px-3 py-2 font-mono text-xs leading-relaxed dark:border-zinc-700 dark:bg-zinc-900"
        />
        <SaveButton onClick={() => save("resume", { resume })} saving={savingKey === "resume"} saved={savedKey === "resume"} />
      </Section>

      {/* Search preferences */}
      <Section title="Job-search preferences" desc="What the daily scraper looks for.">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">Job titles (comma-separated)</span>
            <textarea value={pref("job_titles")} onChange={(e) => setPref("job_titles", e.target.value)} rows={2}
              className="w-full resize-y rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">Locations (comma-separated)</span>
            <textarea value={pref("locations")} onChange={(e) => setPref("locations", e.target.value)} rows={2}
              className="w-full resize-y rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">Earliest start (YYYY-MM)</span>
            <input value={pref("min_start_date")} onChange={(e) => setPref("min_start_date", e.target.value)} placeholder="2027-05"
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">Max jobs per run</span>
            <input type="number" value={pref("max_jobs")} onChange={(e) => setPref("max_jobs", e.target.value)}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-4">
          {BOOL_PREFS.map(([k, label]) => (
            <label key={k} className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <input type="checkbox" checked={pref(k) === "true"} onChange={(e) => setPref(k, e.target.checked ? "true" : "false")} />
              {label}
            </label>
          ))}
        </div>
        <SaveButton onClick={() => save("settings", { settings })} saving={savingKey === "settings"} saved={savedKey === "settings"} />
      </Section>

      {/* Common application answers */}
      <Section title="Common application answers" desc="Reusable answers to questions you get asked on every application.">
        <div className="space-y-4">
          {answers.map((qa, i) => (
            <div key={i} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
              <div className="flex items-start gap-2">
                <input
                  value={qa.q}
                  onChange={(e) => setAnswers((a) => a.map((x, j) => (j === i ? { ...x, q: e.target.value } : x)))}
                  placeholder="Question"
                  className="flex-1 rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium dark:border-zinc-700 dark:bg-zinc-900"
                />
                <button onClick={() => setAnswers((a) => a.filter((_, j) => j !== i))}
                  className="rounded-md px-2 py-1.5 text-xs text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40">
                  Remove
                </button>
              </div>
              <textarea
                value={qa.a}
                onChange={(e) => setAnswers((a) => a.map((x, j) => (j === i ? { ...x, a: e.target.value } : x)))}
                rows={2}
                placeholder="Your answer"
                className="mt-2 w-full resize-y rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              />
            </div>
          ))}
        </div>
        <button onClick={() => setAnswers((a) => [...a, { q: "", a: "" }])}
          className="mt-3 rounded-lg border border-dashed border-zinc-300 px-3 py-1.5 text-sm text-zinc-500 hover:border-zinc-400 dark:border-zinc-700">
          + Add question
        </button>
        <SaveButton onClick={() => save("answers", { answers })} saving={savingKey === "answers"} saved={savedKey === "answers"} />
      </Section>
    </div>
  );
}

const DEFAULT_QUESTIONS = [
  "Why do you want to work here?",
  "Are you authorized to work in the US?",
  "Will you now or in the future require visa sponsorship?",
  "What are your salary expectations?",
  "When are you available to start?",
  "Are you willing to relocate?",
];

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Job } from "@/lib/types";
import { STATUS_LABELS, STATUS_ORDER, STATUS_STYLES, type ApplicationStatus } from "@/lib/types";

function scorePill(score: number | null) {
  if (score == null) return "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400";
  if (score >= 85) return "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300";
  if (score >= 60) return "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300";
  return "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400";
}

export default function JobQuickView({
  job,
  onClose,
  onChanged,
}: {
  job: Job | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [data, setData] = useState<Job | null>(job);
  const [enriching, setEnriching] = useState(false);

  useEffect(() => {
    setData(job);
    if (!job) return;
    // Lazily enrich (summary/company/skills) if not done yet.
    if (!job.enriched_at) {
      setEnriching(true);
      fetch(`/api/jobs/${job.job_id}/enrich`, { method: "POST" })
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => j && setData(j))
        .finally(() => setEnriching(false));
    }
  }, [job]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!job || !data) return null;

  const skills: string[] = (() => {
    try {
      return data.skills ? JSON.parse(data.skills) : [];
    } catch {
      return [];
    }
  })();

  // Enrichment attempted but no result cached => Gemini unavailable (e.g.
  // depleted credits). Distinguish this from a genuinely empty summary.
  const aiUnavailable = !enriching && !data.enriched_at;

  async function setStatus(status: string) {
    await fetch(`/api/jobs/${job!.job_id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ application_status: status }),
    });
    setData((d) => (d ? { ...d, application_status: status as ApplicationStatus } : d));
    onChanged();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 backdrop-blur-sm sm:p-8"
      onClick={onClose}
    >
      <div
        className="relative mt-4 w-full max-w-2xl rounded-2xl border border-zinc-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-950"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Gradient header */}
        <div className="rounded-t-2xl bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-500 p-5 text-white">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold leading-tight">{data.job_title}</h2>
              <p className="mt-0.5 text-sm text-white/85">
                {data.company}
                {data.location ? ` · ${data.location}` : ""}
              </p>
            </div>
            <button
              onClick={onClose}
              className="rounded-full bg-white/20 px-2.5 py-0.5 text-lg leading-none hover:bg-white/30"
              aria-label="Close"
            >
              ×
            </button>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <span className={`rounded-full px-2 py-0.5 font-medium ${scorePill(data.relevance_score)}`}>
              Score {data.relevance_score ?? "—"}
            </span>
            {data.source && (
              <span className="rounded-full bg-white/20 px-2 py-0.5 font-medium">{data.source}</span>
            )}
            {data.date_posted && (
              <span className="rounded-full bg-white/20 px-2 py-0.5">posted {data.date_posted}</span>
            )}
          </div>
        </div>

        <div className="space-y-5 p-5">
          {aiUnavailable && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
              AI summaries are unavailable right now (Gemini API credits depleted). They&apos;ll
              generate automatically once credits are restored.
            </div>
          )}
          {/* Company */}
          <Section title="Company" accent="fuchsia">
            {enriching && !data.company_summary ? (
              <Shimmer />
            ) : (
              <p className="text-sm text-zinc-700 dark:text-zinc-300">
                {data.company_summary || "No company summary available."}
              </p>
            )}
          </Section>

          {/* Role summary */}
          <Section title="Role" accent="indigo">
            {enriching && !data.summary ? (
              <Shimmer />
            ) : (
              <p className="text-sm text-zinc-700 dark:text-zinc-300">
                {data.summary || "No role summary available."}
              </p>
            )}
          </Section>

          {/* Skills */}
          <Section title="Skills they want" accent="emerald">
            {enriching && skills.length === 0 ? (
              <Shimmer />
            ) : skills.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {skills.map((s) => (
                  <span
                    key={s}
                    className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
                  >
                    {s}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-zinc-400">No skills detected.</p>
            )}
          </Section>

          {/* Quick status */}
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Set status</p>
            <div className="flex flex-wrap gap-1.5">
              {STATUS_ORDER.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatus(s)}
                  className={`rounded-full px-2.5 py-1 text-xs font-medium transition ${
                    data.application_status === s
                      ? STATUS_STYLES[s] + " ring-2 ring-offset-1 ring-zinc-400 dark:ring-offset-zinc-950"
                      : "bg-zinc-100 text-zinc-500 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700"
                  }`}
                >
                  {STATUS_LABELS[s]}
                </button>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 border-t border-zinc-100 pt-4 dark:border-zinc-800">
            {data.job_url && (
              <a
                href={data.job_url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-white dark:text-zinc-900"
              >
                Open posting →
              </a>
            )}
            <Link
              href={`/jobs/${data.job_id}`}
              className="text-sm text-indigo-600 hover:underline dark:text-indigo-400"
            >
              Full page & timeline →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({
  title,
  accent,
  children,
}: {
  title: string;
  accent: "indigo" | "fuchsia" | "emerald";
  children: React.ReactNode;
}) {
  const dot = {
    indigo: "bg-indigo-500",
    fuchsia: "bg-fuchsia-500",
    emerald: "bg-emerald-500",
  }[accent];
  return (
    <div>
      <p className="mb-1.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
        <span className={`inline-block h-2 w-2 rounded-full ${dot}`} />
        {title}
      </p>
      {children}
    </div>
  );
}

function Shimmer() {
  return (
    <div className="space-y-2">
      <div className="h-3 w-full animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
      <div className="h-3 w-4/5 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
    </div>
  );
}

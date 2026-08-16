"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Job } from "@/lib/types";
import { STATUS_LABELS, STATUS_ORDER } from "@/lib/types";
import StatusBadge from "./StatusBadge";
import JobQuickView from "./JobQuickView";

type SortKey = "date_found" | "relevance_score" | "company" | "application_status";

function scorePill(score: number | null) {
  if (score == null) return "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400";
  if (score >= 85) return "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300";
  if (score >= 60) return "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300";
  return "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400";
}

export default function JobTable({
  jobs,
  sources,
  locations,
}: {
  jobs: Job[];
  sources: string[];
  locations: string[];
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string>("all");
  const [source, setSource] = useState<string>("all");
  const [location, setLocation] = useState<string>("all");
  const [minScore, setMinScore] = useState(0);
  const [appliedOnly, setAppliedOnly] = useState(false);
  // Default: most recent first.
  const [sortKey, setSortKey] = useState<SortKey>("date_found");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [selected, setSelected] = useState<Job | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = jobs.filter((j) => {
      if (status !== "all" && j.application_status !== status) return false;
      if (source !== "all" && j.source !== source) return false;
      if (location !== "all" && j.location !== location) return false;
      if (minScore > 0 && (j.relevance_score ?? 0) < minScore) return false;
      if (appliedOnly && !j.applied) return false;
      if (q) {
        const hay = `${j.job_title} ${j.company} ${j.location ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    rows.sort((a, b) => {
      let av: string | number = "";
      let bv: string | number = "";
      if (sortKey === "relevance_score") {
        av = a.relevance_score ?? -1;
        bv = b.relevance_score ?? -1;
      } else if (sortKey === "date_found") {
        av = a.date_found ?? "";
        bv = b.date_found ?? "";
      } else if (sortKey === "company") {
        av = a.company?.toLowerCase() ?? "";
        bv = b.company?.toLowerCase() ?? "";
      } else if (sortKey === "application_status") {
        av = STATUS_ORDER.indexOf(a.application_status);
        bv = STATUS_ORDER.indexOf(b.application_status);
      }
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return rows;
  }, [jobs, query, status, source, location, minScore, appliedOnly, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "company" ? "asc" : "desc");
    }
  }
  const arrow = (key: SortKey) => (sortKey === key ? (sortDir === "asc" ? " ↑" : " ↓") : "");

  return (
    <div>
      {/* Controls */}
      <div className="mb-4 flex flex-wrap items-center gap-2.5">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search title, company, location…"
          className="min-w-[220px] flex-1 rounded-lg border border-zinc-300 bg-white px-3.5 py-2.5 text-sm outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-zinc-700 dark:bg-zinc-900"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="all">All statuses</option>
          {STATUS_ORDER.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <select
          value={source}
          onChange={(e) => setSource(e.target.value)}
          className="rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="all">All sources</option>
          {sources.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          className="max-w-[180px] rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="all">All locations</option>
          {locations.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 rounded-lg border border-zinc-300 px-3 py-2.5 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
          <input type="checkbox" checked={appliedOnly} onChange={(e) => setAppliedOnly(e.target.checked)} />
          Applied only
        </label>
        <label className="flex items-center gap-2 rounded-lg border border-zinc-300 px-3 py-2.5 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
          <span className="whitespace-nowrap">Min score</span>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-28 accent-indigo-500"
          />
          <span className="w-7 tabular-nums text-zinc-900 dark:text-zinc-100">{minScore}</span>
        </label>
      </div>

      <div className="mb-2 text-xs text-zinc-500">{filtered.length} jobs · click a row for details</div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-zinc-200 shadow-sm dark:border-zinc-800">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="bg-gradient-to-r from-zinc-50 to-zinc-100 text-left text-xs uppercase tracking-wide text-zinc-500 dark:from-zinc-900 dark:to-zinc-900/40">
            <tr>
              <th className="cursor-pointer px-4 py-3" onClick={() => toggleSort("company")}>
                Company / Role{arrow("company")}
              </th>
              <th className="px-4 py-3">Location</th>
              <th className="cursor-pointer px-4 py-3" onClick={() => toggleSort("relevance_score")}>
                Score{arrow("relevance_score")}
              </th>
              <th className="px-4 py-3">Source</th>
              <th className="cursor-pointer px-4 py-3" onClick={() => toggleSort("date_found")}>
                Added{arrow("date_found")}
              </th>
              <th className="cursor-pointer px-4 py-3" onClick={() => toggleSort("application_status")}>
                Status{arrow("application_status")}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((j) => (
              <tr
                key={j.job_id}
                onClick={() => setSelected(j)}
                className="cursor-pointer border-t border-zinc-100 transition hover:bg-indigo-50/60 dark:border-zinc-800/70 dark:hover:bg-indigo-500/5"
              >
                <td className="px-4 py-3">
                  <div className="font-medium text-zinc-900 dark:text-zinc-100">{j.job_title}</div>
                  <div className="text-zinc-500">{j.company}</div>
                </td>
                <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400">{j.location}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ${scorePill(j.relevance_score)}`}>
                    {j.relevance_score ?? "—"}
                  </span>
                </td>
                <td className="px-4 py-3 text-zinc-500">{j.source}</td>
                <td className="px-4 py-3 text-zinc-500">{j.date_found?.slice(0, 10) || "—"}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={j.application_status} />
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-zinc-400">
                  No jobs match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <JobQuickView
        job={selected}
        onClose={() => setSelected(null)}
        onChanged={() => router.refresh()}
      />
    </div>
  );
}

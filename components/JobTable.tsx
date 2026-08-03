"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { Job } from "@/lib/types";
import { STATUS_LABELS, STATUS_ORDER } from "@/lib/types";
import StatusBadge from "./StatusBadge";

type SortKey = "relevance_score" | "date_posted" | "company" | "application_status";

export default function JobTable({ jobs, sources }: { jobs: Job[]; sources: string[] }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string>("all");
  const [source, setSource] = useState<string>("all");
  const [appliedOnly, setAppliedOnly] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("relevance_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let rows = jobs.filter((j) => {
      if (status !== "all" && j.application_status !== status) return false;
      if (source !== "all" && j.source !== source) return false;
      if (appliedOnly && !j.applied) return false;
      if (q) {
        const hay = `${j.job_title} ${j.company} ${j.location ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    rows = [...rows].sort((a, b) => {
      let av: string | number = "";
      let bv: string | number = "";
      if (sortKey === "relevance_score") {
        av = a.relevance_score ?? -1;
        bv = b.relevance_score ?? -1;
      } else if (sortKey === "date_posted") {
        av = a.date_posted ?? "";
        bv = b.date_posted ?? "";
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
  }, [jobs, query, status, source, appliedOnly, sortKey, sortDir]);

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
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search title, company, location…"
          className="min-w-[220px] flex-1 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
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
          className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="all">All sources</option>
          {sources.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
          <input
            type="checkbox"
            checked={appliedOnly}
            onChange={(e) => setAppliedOnly(e.target.checked)}
          />
          Applied only
        </label>
        <span className="text-sm text-zinc-500">{filtered.length} jobs</span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900/60">
            <tr>
              <th className="cursor-pointer px-4 py-3" onClick={() => toggleSort("company")}>
                Company / Role{arrow("company")}
              </th>
              <th className="px-4 py-3">Location</th>
              <th className="cursor-pointer px-4 py-3" onClick={() => toggleSort("relevance_score")}>
                Score{arrow("relevance_score")}
              </th>
              <th className="px-4 py-3">Source</th>
              <th className="cursor-pointer px-4 py-3" onClick={() => toggleSort("date_posted")}>
                Posted{arrow("date_posted")}
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
                className="border-t border-zinc-100 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900/40"
              >
                <td className="px-4 py-3">
                  <Link href={`/jobs/${j.job_id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-100">
                    {j.job_title}
                  </Link>
                  <div className="text-zinc-500">{j.company}</div>
                </td>
                <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400">{j.location}</td>
                <td className="px-4 py-3 tabular-nums">{j.relevance_score ?? "—"}</td>
                <td className="px-4 py-3 text-zinc-500">{j.source}</td>
                <td className="px-4 py-3 text-zinc-500">{j.date_posted || "—"}</td>
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
    </div>
  );
}

import Link from "next/link";
import { getProgress, getActivePipeline } from "@/lib/queries";
import ProgressChart from "@/components/ProgressChart";
import StatTile from "@/components/StatTile";
import StatusBadge from "@/components/StatusBadge";
import { STATUS_LABELS, STATUS_ORDER, STATUS_STYLES, type ApplicationStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [p, pipeline] = await Promise.all([getProgress(), getActivePipeline()]);

  const funnel = STATUS_ORDER.filter((s) => s !== "not_applied" && s !== "skipped").map((s) => ({
    status: s,
    count: p.statusCounts[s] ?? 0,
  }));
  const maxFunnel = Math.max(...funnel.map((f) => f.count), 1);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-1 text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
        Application Progress
      </h1>
      <p className="mb-6 text-sm text-zinc-500">Your application activity over time.</p>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Total applications" value={p.total} gradient="from-indigo-500 to-violet-500" />
        <StatTile label="Active days" value={p.activeDays} gradient="from-violet-500 to-fuchsia-500" />
        <StatTile label="Average / day" value={p.avgPerDay} gradient="from-fuchsia-500 to-rose-500" />
        <StatTile label="Skipped" value={p.statusCounts["skipped"] ?? 0} gradient="from-zinc-400 to-zinc-500" />
      </div>

      {/* Active pipeline — quick access to interview/assessment companies */}
      <section className="mb-8 rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Interviews &amp; Assessments
        </h2>
        {pipeline.length === 0 ? (
          <p className="text-sm text-zinc-400">
            No jobs currently marked interview or assessment.
          </p>
        ) : (
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800/70">
            {pipeline.map((j) => {
              const link = j.action_url || j.job_url;
              return (
                <li key={j.job_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-3">
                  <StatusBadge status={j.application_status} />
                  <div className="min-w-0 flex-1">
                    <Link
                      href={`/jobs/${j.job_id}`}
                      className="font-medium text-zinc-900 hover:underline dark:text-zinc-100"
                    >
                      {j.company}
                    </Link>
                    <span className="ml-2 text-sm text-zinc-500">{j.job_title}</span>
                  </div>
                  {link && (
                    <a
                      href={link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 text-sm text-indigo-500 hover:underline"
                    >
                      Open posting ↗
                    </a>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="mb-8 rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Applications over time
        </h2>
        <ProgressChart daily={p.daily} />
      </section>

      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
        {/* Funnel */}
        <section className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Pipeline
          </h2>
          <ul className="space-y-3">
            {funnel.map((f) => (
              <li key={f.status} className="flex items-center gap-3">
                <span className="w-24 shrink-0 text-sm text-zinc-600 dark:text-zinc-400">
                  {STATUS_LABELS[f.status as ApplicationStatus]}
                </span>
                <div className="h-6 flex-1 overflow-hidden rounded-md bg-zinc-100 dark:bg-zinc-900">
                  <div
                    className={`flex h-full items-center justify-end rounded-md px-2 text-xs font-semibold ${STATUS_STYLES[f.status as ApplicationStatus]}`}
                    style={{ width: `${Math.max((f.count / maxFunnel) * 100, f.count > 0 ? 12 : 0)}%` }}
                  >
                    {f.count > 0 ? f.count : ""}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>

        {/* Daily table */}
        <section className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Daily log
          </h2>
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-zinc-400">
              <tr>
                <th className="pb-2">Date</th>
                <th className="pb-2 text-right">Applications</th>
                <th className="pb-2 text-right">Cumulative</th>
              </tr>
            </thead>
            <tbody>
              {[...p.daily].reverse().map((d) => (
                <tr key={d.iso} className="border-t border-zinc-100 dark:border-zinc-800/70">
                  <td className="py-2 text-zinc-600 dark:text-zinc-400">{d.label}</td>
                  <td className="py-2 text-right font-medium tabular-nums">{d.count}</td>
                  <td className="py-2 text-right tabular-nums text-zinc-500">{d.cumulative}</td>
                </tr>
              ))}
              {p.daily.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-6 text-center text-zinc-400">
                    No applications logged yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      </div>
    </main>
  );
}

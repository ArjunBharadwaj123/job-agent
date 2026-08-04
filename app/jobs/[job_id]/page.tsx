import Link from "next/link";
import { notFound } from "next/navigation";
import { getJob, getStatusEvents } from "@/lib/queries";
import StatusBadge from "@/components/StatusBadge";
import StatusControls from "@/components/StatusControls";
import Timeline from "@/components/Timeline";

export const dynamic = "force-dynamic";

export default async function JobDetail({
  params,
}: {
  params: Promise<{ job_id: string }>;
}) {
  const { job_id } = await params;
  const [job, events] = await Promise.all([getJob(job_id), getStatusEvents(job_id)]);
  if (!job) notFound();

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <Link href="/jobs" className="text-sm text-zinc-500 hover:underline">
        ← All jobs
      </Link>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
            {job.job_title}
          </h1>
          <p className="mt-1 text-zinc-500">
            {job.company}
            {job.location ? ` · ${job.location}` : ""}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-zinc-500">
            <StatusBadge status={job.application_status} />
            {job.relevance_score != null && <span>Score {job.relevance_score}</span>}
            {job.source && <span>· {job.source}</span>}
            {job.date_posted && <span>· posted {job.date_posted}</span>}
          </div>
        </div>
        <div className="flex gap-2">
          {job.job_url && (
            <a
              href={job.job_url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
            >
              Open posting →
            </a>
          )}
        </div>
      </div>

      {/* Action link surfaced from an email (assessment / interview) */}
      {job.action_url && (
        <a
          href={job.action_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-block rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
        >
          {job.action_type === "assessment" ? "Take assessment" : "Open interview link"} →
        </a>
      )}

      <div className="mt-8 grid grid-cols-1 gap-8 md:grid-cols-3">
        {/* Left: description */}
        <section className="md:col-span-2">
          <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-zinc-500">
            Details
          </h2>
          <dl className="mb-6 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <Field label="Applied" value={job.applied ? "Yes" : "No"} />
            <Field label="Date applied" value={job.date_applied || "—"} />
            <Field label="Priority" value={job.priority || "—"} />
            <Field label="Role type" value={job.role_type || "—"} />
            <Field label="Found" value={job.date_found?.slice(0, 10) || "—"} />
            <Field label="Confidence" value={job.confidence != null ? `${job.confidence}` : "—"} />
          </dl>

          <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-zinc-500">
            Status history
          </h2>
          <Timeline events={events} />
        </section>

        {/* Right: controls */}
        <aside>
          <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-zinc-500">
            Application
          </h2>
          <StatusControls job={job} />
        </aside>
      </div>
    </main>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-zinc-400">{label}</dt>
      <dd className="text-zinc-800 dark:text-zinc-200">{value}</dd>
    </div>
  );
}

import { getJobs, getFacets } from "@/lib/queries";
import JobTable from "@/components/JobTable";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [jobs, facets] = await Promise.all([getJobs(), getFacets()]);

  const applied = jobs.filter((j) => j.applied).length;
  const active = jobs.filter((j) =>
    ["assessment", "interview"].includes(j.application_status)
  ).length;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          Job Dashboard
        </h1>
        <p className="mt-1 text-sm text-zinc-500">
          {jobs.length} jobs · {applied} applied · {active} in assessment/interview
        </p>
      </header>
      <JobTable jobs={jobs} sources={facets.sources} />
    </main>
  );
}

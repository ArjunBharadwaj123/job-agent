import { getJobs, getFacets } from "@/lib/queries";
import JobTable from "@/components/JobTable";
import StatTile from "@/components/StatTile";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [jobs, facets] = await Promise.all([getJobs(), getFacets()]);

  const applied = jobs.filter((j) => j.applied).length;
  const active = jobs.filter((j) =>
    ["assessment", "interview"].includes(j.application_status)
  ).length;
  const offers = jobs.filter((j) => j.application_status === "accepted").length;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Total jobs" value={jobs.length} gradient="from-indigo-500 to-violet-500" />
        <StatTile label="Applied" value={applied} gradient="from-blue-500 to-cyan-500" />
        <StatTile label="Assess / Interview" value={active} gradient="from-violet-500 to-fuchsia-500" />
        <StatTile label="Offers" value={offers} gradient="from-emerald-500 to-teal-500" />
      </div>
      <JobTable jobs={jobs} sources={facets.sources} />
    </main>
  );
}

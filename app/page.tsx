import { getJobs, getFacets, getStats } from "@/lib/queries";
import JobTable from "@/components/JobTable";
import StatTile from "@/components/StatTile";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [jobs, facets, stats] = await Promise.all([getJobs(), getFacets(), getStats()]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Total jobs" value={stats.total} gradient="from-indigo-500 to-violet-500" />
        <StatTile label="Applied" value={stats.applied} gradient="from-blue-500 to-cyan-500" />
        <StatTile label="Assess / Interview" value={stats.active} gradient="from-violet-500 to-fuchsia-500" />
        <StatTile label="Offers" value={stats.offers} gradient="from-emerald-500 to-teal-500" />
      </div>
      <JobTable jobs={jobs} sources={facets.sources} />
    </main>
  );
}

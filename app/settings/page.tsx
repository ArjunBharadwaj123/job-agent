import { getResources } from "@/lib/queries";
import SettingsForm from "@/components/SettingsForm";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const resources = await getResources();
  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <h1 className="mb-1 text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
        Settings &amp; Resources
      </h1>
      <p className="mb-6 text-sm text-zinc-500">
        Your resume, saved answers to common application questions, and job-search
        preferences. The resume feeds job-match scoring.
      </p>
      <SettingsForm initial={resources} />
    </main>
  );
}

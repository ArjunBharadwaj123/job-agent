import type { StatusEvent } from "@/lib/types";
import { STATUS_LABELS, type ApplicationStatus } from "@/lib/types";

function label(s: string | null) {
  if (!s) return "—";
  return STATUS_LABELS[s as ApplicationStatus] ?? s;
}

export default function Timeline({ events }: { events: StatusEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-zinc-400">No status history yet.</p>;
  }
  return (
    <ol className="space-y-4">
      {events.map((e) => (
        <li key={e.id} className="relative border-l-2 border-zinc-200 pl-4 dark:border-zinc-800">
          <div className="absolute -left-[7px] top-1 h-3 w-3 rounded-full bg-zinc-400 dark:bg-zinc-600" />
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium text-zinc-900 dark:text-zinc-100">
              {label(e.old_status)} → {label(e.new_status)}
            </span>
            {e.source && (
              <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs text-zinc-500 dark:bg-zinc-800">
                {e.source}
              </span>
            )}
            {e.needs_review === 1 && (
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                needs review
              </span>
            )}
            {e.confidence != null && (
              <span className="text-xs text-zinc-400">
                {Math.round(e.confidence * 100)}% confidence
              </span>
            )}
          </div>
          {e.reasoning && (
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{e.reasoning}</p>
          )}
          {e.action_url && (
            <a
              href={e.action_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-block rounded-md bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-500"
            >
              Open {e.action_type ?? "link"} →
            </a>
          )}
          {e.email_thread_url && (
            <a
              href={e.email_thread_url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 mt-1 inline-block text-xs text-zinc-500 underline"
            >
              View email
            </a>
          )}
          <div className="mt-1 text-xs text-zinc-400">
            {e.created_at ? new Date(e.created_at).toLocaleString() : ""}
          </div>
        </li>
      ))}
    </ol>
  );
}

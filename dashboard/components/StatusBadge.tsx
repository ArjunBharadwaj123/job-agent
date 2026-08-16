import { STATUS_LABELS, STATUS_STYLES, type ApplicationStatus } from "@/lib/types";

export default function StatusBadge({ status }: { status: string }) {
  const s = (status as ApplicationStatus) in STATUS_LABELS ? (status as ApplicationStatus) : "not_applied";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[s]}`}
    >
      {STATUS_LABELS[s] ?? status}
    </span>
  );
}

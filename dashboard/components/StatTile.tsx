export default function StatTile({
  label,
  value,
  gradient,
}: {
  label: string;
  value: number | string;
  gradient: string;
}) {
  return (
    <div className={`rounded-2xl bg-gradient-to-br ${gradient} p-[1px] shadow-sm`}>
      <div className="flex h-full flex-col justify-between rounded-2xl bg-white p-4 dark:bg-zinc-950">
        <span className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</span>
        <span
          className={`mt-2 bg-gradient-to-br ${gradient} bg-clip-text text-3xl font-bold tabular-nums text-transparent`}
        >
          {value}
        </span>
      </div>
    </div>
  );
}

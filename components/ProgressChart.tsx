import type { ProgressData } from "@/lib/queries";

// Pure-SVG chart: daily application bars + a cumulative line overlay.
export default function ProgressChart({ daily }: { daily: ProgressData["daily"] }) {
  if (daily.length === 0) {
    return <p className="text-sm text-zinc-400">No applications logged yet.</p>;
  }

  const W = 720;
  const H = 260;
  const padL = 32;
  const padR = 16;
  const padT = 16;
  const padB = 28;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const maxCount = Math.max(...daily.map((d) => d.count), 1);
  const maxCum = Math.max(...daily.map((d) => d.cumulative), 1);
  const n = daily.length;
  const slot = plotW / n;
  const barW = Math.min(slot * 0.6, 48);

  const x = (i: number) => padL + slot * i + slot / 2;
  const yBar = (c: number) => padT + plotH - (c / maxCount) * plotH;
  const yCum = (c: number) => padT + plotH - (c / maxCum) * plotH;

  const linePath = daily
    .map((d, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${yCum(d.cumulative).toFixed(1)}`)
    .join(" ");

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="min-w-[560px] w-full" role="img" aria-label="Applications over time">
        {/* baseline */}
        <line x1={padL} y1={padT + plotH} x2={W - padR} y2={padT + plotH} className="stroke-zinc-200 dark:stroke-zinc-800" strokeWidth={1} />

        {daily.map((d, i) => {
          const h = padT + plotH - yBar(d.count);
          return (
            <g key={d.iso}>
              <rect
                x={x(i) - barW / 2}
                y={yBar(d.count)}
                width={barW}
                height={Math.max(h, 0)}
                rx={3}
                className="fill-indigo-500/80"
              />
              <text x={x(i)} y={yBar(d.count) - 5} textAnchor="middle" className="fill-zinc-500 text-[11px]">
                {d.count}
              </text>
              <text x={x(i)} y={H - 8} textAnchor="middle" className="fill-zinc-400 text-[11px]">
                {d.label}
              </text>
            </g>
          );
        })}

        {/* cumulative line */}
        <path d={linePath} fill="none" className="stroke-emerald-500" strokeWidth={2} />
        {daily.map((d, i) => (
          <circle key={d.iso} cx={x(i)} cy={yCum(d.cumulative)} r={3} className="fill-emerald-500" />
        ))}
      </svg>
      <div className="mt-1 flex gap-4 text-xs text-zinc-500">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-indigo-500/80" /> Applications / day
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500" /> Cumulative
        </span>
      </div>
    </div>
  );
}

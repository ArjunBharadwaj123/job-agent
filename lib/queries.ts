import { db } from "./db";
import type { ResultSet } from "@libsql/client";
import type { Job, StatusEvent, ApplicationStatus } from "./types";

// libSQL Row objects aren't plain objects, so they can't be passed from server
// components to client components. Rebuild each row as a plain record keyed by
// column name.
function rows<T>(rs: ResultSet): T[] {
  return rs.rows.map((row) => {
    const obj: Record<string, unknown> = {};
    rs.columns.forEach((col, i) => {
      obj[col] = (row as unknown as unknown[])[i];
    });
    return obj as T;
  });
}

export async function getJobs(): Promise<Job[]> {
  const rs = await db.execute(
    `SELECT * FROM jobs WHERE archived = 0 ORDER BY date_found DESC, relevance_score DESC`
  );
  return rows<Job>(rs);
}

export async function getJob(jobId: string): Promise<Job | null> {
  const rs = await db.execute({
    sql: `SELECT * FROM jobs WHERE job_id = ?`,
    args: [jobId],
  });
  return rows<Job>(rs)[0] ?? null;
}

export async function getStatusEvents(jobId: string): Promise<StatusEvent[]> {
  const rs = await db.execute({
    sql: `SELECT * FROM status_events WHERE job_id = ? ORDER BY created_at DESC, id DESC`,
    args: [jobId],
  });
  return rows<StatusEvent>(rs);
}

export interface UserFieldUpdate {
  application_status?: ApplicationStatus;
  applied?: boolean;
  priority?: string | null;
  notes?: string | null;
  date_applied?: string | null;
  locked?: boolean;
}

// Writes only user-owned columns. Records a manual status_event when the
// application_status changes.
export async function updateUserFields(jobId: string, patch: UserFieldUpdate) {
  const now = new Date().toISOString();

  const current = await getJob(jobId);
  if (!current) throw new Error("job not found");

  const sets: string[] = [];
  const args: (string | number | null)[] = [];

  if (patch.application_status !== undefined) {
    sets.push("application_status = ?");
    args.push(patch.application_status);
    // Marking anything past not_applied implies applied=1 + a date_applied.
    if (patch.application_status !== "not_applied" && !current.applied) {
      sets.push("applied = 1");
      if (!current.date_applied) {
        sets.push("date_applied = ?");
        args.push(now.slice(0, 10));
      }
    }
  }
  if (patch.applied !== undefined) {
    sets.push("applied = ?");
    args.push(patch.applied ? 1 : 0);
    if (patch.applied && !current.date_applied) {
      sets.push("date_applied = ?");
      args.push(now.slice(0, 10));
    }
  }
  if (patch.priority !== undefined) {
    sets.push("priority = ?");
    args.push(patch.priority);
  }
  if (patch.notes !== undefined) {
    sets.push("notes = ?");
    args.push(patch.notes);
  }
  if (patch.date_applied !== undefined) {
    sets.push("date_applied = ?");
    args.push(patch.date_applied);
  }
  if (patch.locked !== undefined) {
    sets.push("locked = ?");
    args.push(patch.locked ? 1 : 0);
  }

  if (sets.length === 0) return current;

  sets.push("last_updated = ?");
  args.push(now);
  args.push(jobId);

  await db.execute({
    sql: `UPDATE jobs SET ${sets.join(", ")} WHERE job_id = ?`,
    args,
  });

  // Append a manual timeline entry when status actually changed.
  if (
    patch.application_status !== undefined &&
    patch.application_status !== current.application_status
  ) {
    await db.execute({
      sql: `INSERT INTO status_events
              (job_id, old_status, new_status, source, needs_review, created_at)
            VALUES (?, ?, ?, 'manual', 0, ?)`,
      args: [jobId, current.application_status, patch.application_status, now],
    });
  }

  return getJob(jobId);
}

// Lazy, keyless enrichment: fetch the posting text (if we don't have it),
// derive a brief + skills from it, pull a company blurb from Wikipedia, cache
// it on the row, and return the job. No LLM / API key required.
export async function enrichJobIfNeeded(jobId: string): Promise<Job | null> {
  const { fetchJobText } = await import("./fetchJob");
  const { extractSkills, briefFromText } = await import("./skills");
  const { wikiSummary } = await import("./wikipedia");

  const job = await getJob(jobId);
  if (!job) return null;
  if (job.enriched_at) return job; // already enriched

  let description = job.description || "";
  if (!description && job.job_url) {
    description = await fetchJobText(job.job_url);
  }

  const [companySummary, skills, brief] = await Promise.all([
    wikiSummary(job.company),
    Promise.resolve(extractSkills(`${description} ${job.job_title}`)),
    Promise.resolve(briefFromText(description)),
  ]);

  const now = new Date().toISOString();
  await db.execute({
    sql: `UPDATE jobs SET description = ?, summary = ?, company_summary = ?,
                 skills = ?, enriched_at = ? WHERE job_id = ?`,
    args: [
      description || null,
      brief || null,
      companySummary || null,
      JSON.stringify(skills),
      now,
      jobId,
    ],
  });
  return getJob(jobId);
}

export interface ProgressData {
  daily: { iso: string; label: string; count: number; cumulative: number }[];
  total: number;
  activeDays: number;
  avgPerDay: number;
  statusCounts: Record<string, number>;
}

// date_applied is stored as US-style M/D/YYYY -> normalize to YYYY-MM-DD.
function toIso(raw: string): string | null {
  const parts = raw.trim().split("/");
  if (parts.length !== 3) return null;
  const [m, d, y] = parts.map((p) => parseInt(p, 10));
  if (!m || !d || !y) return null;
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

export async function getProgress(): Promise<ProgressData> {
  const rs = await db.execute(
    `SELECT date_applied FROM jobs WHERE applied = 1 AND date_applied IS NOT NULL AND date_applied != ''`
  );
  const counts = new Map<string, number>();
  for (const row of rs.rows) {
    const iso = toIso((row as unknown as { date_applied: string }).date_applied);
    if (!iso) continue;
    counts.set(iso, (counts.get(iso) ?? 0) + 1);
  }
  const isoKeys = [...counts.keys()].sort();
  let cum = 0;
  const daily = isoKeys.map((iso) => {
    const count = counts.get(iso)!;
    cum += count;
    const [, m, d] = iso.split("-");
    return { iso, label: `${Number(m)}/${Number(d)}`, count, cumulative: cum };
  });
  const total = cum;
  const activeDays = isoKeys.length;

  const statusRs = await db.execute(
    `SELECT application_status AS s, COUNT(*) AS c FROM jobs GROUP BY application_status`
  );
  const statusCounts: Record<string, number> = {};
  for (const r of statusRs.rows) {
    const row = r as unknown as { s: string; c: number };
    statusCounts[row.s] = Number(row.c);
  }

  return {
    daily,
    total,
    activeDays,
    avgPerDay: activeDays ? Math.round((total / activeDays) * 10) / 10 : 0,
    statusCounts,
  };
}

export interface JobFacets {
  sources: string[];
  statuses: string[];
}

export async function getFacets(): Promise<JobFacets> {
  const [srcRs, statRs] = await Promise.all([
    db.execute(`SELECT DISTINCT source FROM jobs WHERE source IS NOT NULL AND source != '' ORDER BY source`),
    db.execute(`SELECT DISTINCT application_status FROM jobs ORDER BY application_status`),
  ]);
  return {
    sources: srcRs.rows.map((r) => r.source as string),
    statuses: statRs.rows.map((r) => r.application_status as string),
  };
}

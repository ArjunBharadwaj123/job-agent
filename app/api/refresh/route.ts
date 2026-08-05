import { NextResponse } from "next/server";

export const runtime = "nodejs";

// Triggers the job-agent GitHub Actions workflows on demand (the scrape's daily
// schedule was removed in favor of this button) and reports run status/ETA.
const OWNER = "ArjunBharadwaj123";
const REPO = "job-agent";
const SCRAPE = "daily_scrape.yml";
const EMAIL = "daily_email_scan.yml";
const FALLBACK_ETA = 540; // ~9 min if we have no prior run to estimate from

interface RunInfo {
  status: string | null; // queued | in_progress | completed | null
  conclusion: string | null; // success | failure | ... | null
  run_started_at: string | null;
  html_url: string | null;
}

function gh(path: string, init?: RequestInit) {
  const token = process.env.GH_DISPATCH_TOKEN;
  if (!token) throw new Error("GH_DISPATCH_TOKEN not set");
  return fetch(`https://api.github.com${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "jobtrail-dashboard",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
}

async function latestRuns(workflow: string, perPage = 10) {
  const res = await gh(
    `/repos/${OWNER}/${REPO}/actions/workflows/${workflow}/runs?event=workflow_dispatch&per_page=${perPage}`
  );
  if (!res.ok) return [];
  const data = await res.json();
  return (data.workflow_runs || []) as Array<{
    status: string;
    conclusion: string | null;
    run_started_at: string;
    updated_at: string;
    html_url: string;
  }>;
}

function toInfo(run?: { status: string; conclusion: string | null; run_started_at: string; html_url: string }): RunInfo {
  if (!run) return { status: null, conclusion: null, run_started_at: null, html_url: null };
  return {
    status: run.status,
    conclusion: run.conclusion,
    run_started_at: run.run_started_at,
    html_url: run.html_url,
  };
}

function isActive(run?: { status: string }) {
  return run?.status === "queued" || run?.status === "in_progress";
}

export async function POST() {
  try {
    // Dispatch each workflow only if it isn't already running.
    for (const wf of [SCRAPE, EMAIL]) {
      const runs = await latestRuns(wf, 1);
      if (isActive(runs[0])) continue;
      const res = await gh(`/repos/${OWNER}/${REPO}/actions/workflows/${wf}/dispatches`, {
        method: "POST",
        body: JSON.stringify({ ref: "main" }),
      });
      if (!res.ok && res.status !== 204) {
        const body = await res.text();
        return NextResponse.json({ error: `dispatch ${wf} failed: ${res.status} ${body.slice(0, 120)}` }, { status: 502 });
      }
    }
    return NextResponse.json({ dispatched: true });
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "dispatch failed" }, { status: 500 });
  }
}

export async function GET() {
  try {
    const [scrapeRuns, emailRuns] = await Promise.all([latestRuns(SCRAPE), latestRuns(EMAIL)]);
    // ETA = duration of the last completed scrape run.
    const lastDone = scrapeRuns.find((r) => r.status === "completed");
    let etaSeconds = FALLBACK_ETA;
    if (lastDone) {
      const dur = (Date.parse(lastDone.updated_at) - Date.parse(lastDone.run_started_at)) / 1000;
      if (dur > 30 && dur < 3600) etaSeconds = Math.round(dur);
    }
    return NextResponse.json({
      scrape: toInfo(scrapeRuns[0]),
      email: toInfo(emailRuns[0]),
      etaSeconds,
    });
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "status failed" }, { status: 500 });
  }
}

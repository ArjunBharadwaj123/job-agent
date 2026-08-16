import { NextRequest, NextResponse } from "next/server";
import { enrichJobIfNeeded } from "@/lib/queries";

export const runtime = "nodejs";
export const maxDuration = 30;

// POST /api/jobs/:id/enrich — lazily generates + caches the AI summary,
// company blurb, and skills for a job, then returns the full row.
export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ job_id: string }> }
) {
  const { job_id } = await params;
  try {
    const job = await enrichJobIfNeeded(job_id);
    if (!job) return NextResponse.json({ error: "not found" }, { status: 404 });
    return NextResponse.json(job);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "enrich failed" },
      { status: 500 }
    );
  }
}

import { NextRequest, NextResponse } from "next/server";
import { createJob } from "@/lib/queries";

export const runtime = "nodejs";

// POST /api/jobs { title, company, location?, job_url?, description? } -> create
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    if (!body.title?.trim() || !body.company?.trim()) {
      return NextResponse.json({ error: "title and company are required" }, { status: 400 });
    }
    const result = await createJob(body);
    return NextResponse.json(result);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "create failed" },
      { status: 400 }
    );
  }
}

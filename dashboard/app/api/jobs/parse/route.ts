import { NextRequest, NextResponse } from "next/server";
import { extractJobPosting } from "@/lib/fetchJob";

export const runtime = "nodejs";
export const maxDuration = 20;

// POST /api/jobs/parse { url } -> best-effort { title, company, location, description }
export async function POST(req: NextRequest) {
  try {
    const { url } = await req.json();
    if (!url || typeof url !== "string") {
      return NextResponse.json({ error: "url required" }, { status: 400 });
    }
    const parsed = await extractJobPosting(url);
    return NextResponse.json(parsed);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "parse failed" },
      { status: 500 }
    );
  }
}

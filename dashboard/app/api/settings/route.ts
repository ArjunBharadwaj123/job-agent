import { NextRequest, NextResponse } from "next/server";
import { saveResources, getResources } from "@/lib/queries";

export const runtime = "nodejs";

export async function PATCH(req: NextRequest) {
  try {
    const body = await req.json();
    await saveResources(body);
    return NextResponse.json(await getResources());
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "save failed" },
      { status: 400 }
    );
  }
}

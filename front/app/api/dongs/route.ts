import { NextResponse } from "next/server";

import { loadIndex } from "@/lib/data";

export const dynamic = "force-dynamic";

export async function GET() {
  const { meta, dongs, centers, source } = await loadIndex();
  return NextResponse.json({ source, meta, dongs, centers });
}

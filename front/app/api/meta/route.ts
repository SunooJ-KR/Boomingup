import { NextResponse } from "next/server";

import { loadMeta } from "@/lib/data";

export const dynamic = "force-dynamic";

export async function GET() {
  const { meta, source } = await loadMeta();
  return NextResponse.json({ source, meta });
}

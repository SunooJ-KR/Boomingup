import { NextResponse } from "next/server";

import { loadDongDetail, loadMeta } from "@/lib/data";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ dongId: string }> },
) {
  const { dongId } = await params;
  // 기준 분기를 넘겨받으면 메타를 다시 읽지 않는다
  const asOfParam = new URL(request.url).searchParams.get("asOf");
  const asOfQuarter = asOfParam ?? (await loadMeta()).meta.as_of_quarter;

  const { detail, source } = await loadDongDetail(decodeURIComponent(dongId), asOfQuarter);
  if (!detail) {
    return NextResponse.json({ error: "해당 동의 상세 정보를 찾지 못했습니다." }, { status: 404 });
  }
  return NextResponse.json({ source, detail });
}

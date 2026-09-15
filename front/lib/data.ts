import "server-only";

// DB(active snapshot)를 먼저 읽고, 접속이 없거나 조회가 실패하면 샘플 JSON으로 폴백한다.
// 화면이 비지 않게 하는 것이 목적이라, 폴백했다는 사실을 source로 같이 돌려준다.
import dongDetailsJson from "@/public/data/dong-details.json";
import dongsJson from "@/public/data/dongs.json";
import metaJson from "@/public/data/meta.json";

import { fetchDongCenters, fetchDongDetail, fetchDongs, fetchMeta } from "./queries";
import type { DongDetail, DongSummary, Meta } from "./types";

export type DataSource = "db" | "sample";

const sampleDongs = dongsJson as DongSummary[];
const sampleDetails = dongDetailsJson as unknown as Record<string, DongDetail>;
const sampleMeta = metaJson as Meta;

export type IndexData = {
  meta: Meta;
  dongs: DongSummary[];
  centers: Record<string, { lat: number; lng: number }>;
  source: DataSource;
};

export async function loadIndex(): Promise<IndexData> {
  try {
    const meta = await fetchMeta();
    const [dongs, centers] = await Promise.all([fetchDongs(meta.as_of_quarter), fetchDongCenters()]);
    if (dongs.length === 0) throw new Error("active snapshot에 동 목록이 없습니다.");
    return { meta, dongs, centers, source: "db" };
  } catch (error) {
    warnFallback("동 목록", error);
    return { meta: sampleMeta, dongs: sampleDongs, centers: {}, source: "sample" };
  }
}

export type DetailData = {
  detail: DongDetail | null;
  source: DataSource;
};

export async function loadDongDetail(dongId: string, asOfQuarter: string): Promise<DetailData> {
  try {
    return { detail: await fetchDongDetail(dongId, asOfQuarter), source: "db" };
  } catch (error) {
    warnFallback(`${dongId} 상세`, error);
    return { detail: sampleDetails[dongId] ?? null, source: "sample" };
  }
}

export async function loadMeta(): Promise<{ meta: Meta; source: DataSource }> {
  try {
    return { meta: await fetchMeta(), source: "db" };
  } catch (error) {
    warnFallback("메타", error);
    return { meta: sampleMeta, source: "sample" };
  }
}

/** 필터 UI에 쓸 자치구 목록 */
export function guNamesOf(dongs: DongSummary[]): string[] {
  return [...new Set(dongs.map((dong) => dong.gu_name))].sort((a, b) => a.localeCompare(b, "ko"));
}

/** 필터 UI에 쓸 지역 태그 목록 */
export function tagsOf(dongs: DongSummary[]): string[] {
  return [...new Set(dongs.flatMap((dong) => dong.tags ?? []))].sort((a, b) =>
    a.localeCompare(b, "ko"),
  );
}

function warnFallback(what: string, error: unknown) {
  console.warn(`[data] ${what} DB 조회 실패, 샘플 JSON으로 폴백합니다.`, error);
}

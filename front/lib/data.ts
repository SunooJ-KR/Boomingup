// 지금은 샘플 JSON을 그대로 import한다.
// 실제 데이터로 바꿀 때는 이 파일의 함수 본문만 API 호출이나 public/data fetch로 교체하면 된다.
import dongDetailsJson from "@/public/data/dong-details.json";
import dongsJson from "@/public/data/dongs.json";
import metaJson from "@/public/data/meta.json";

import type { DongDetail, DongSummary, Meta } from "./types";

const dongs = dongsJson as DongSummary[];
const details = dongDetailsJson as unknown as Record<string, DongDetail>;
const meta = metaJson as Meta;

export function getMeta(): Meta {
  return meta;
}

export function getDongs(): DongSummary[] {
  return dongs;
}

export function getDongDetail(dongId: string): DongDetail | null {
  return details[dongId] ?? null;
}

/** 필터 UI에 쓸 자치구 목록 */
export function getGuNames(): string[] {
  return [...new Set(dongs.map((dong) => dong.gu_name))].sort((a, b) => a.localeCompare(b, "ko"));
}

/** 필터 UI에 쓸 지역 태그 목록 */
export function getTags(): string[] {
  return [...new Set(dongs.flatMap((dong) => dong.tags ?? []))].sort((a, b) =>
    a.localeCompare(b, "ko"),
  );
}

/** 샘플 단계에서는 상세 데이터를 한 번에 넘긴다. 실제 데이터에서는 선택 시점에 불러오도록 바꾼다. */
export function getAllDongDetails(): Record<string, DongDetail> {
  return details;
}

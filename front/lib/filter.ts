import type { DongSummary, PredictionStatus } from "./types";

export type DongFilter = {
  query: string;
  gu: string | null;
  statuses: PredictionStatus[];
  tags: string[];
};

export const EMPTY_FILTER: DongFilter = { query: "", gu: null, statuses: [], tags: [] };

/** 검색어는 동 이름과 자치구 이름 모두에 걸린다. 선택하지 않은 필터는 조건에서 빠진다. */
export function filterDongs(dongs: DongSummary[], filter: DongFilter): DongSummary[] {
  const query = filter.query.trim();
  return dongs.filter((dong) => {
    if (query && !`${dong.gu_name} ${dong.umd_name}`.includes(query)) return false;
    if (filter.gu && dong.gu_name !== filter.gu) return false;
    if (filter.statuses.length > 0 && !filter.statuses.includes(dong.status)) return false;
    if (filter.tags.length > 0) {
      const tags = dong.tags ?? [];
      if (!filter.tags.every((tag) => tags.includes(tag))) return false;
    }
    return true;
  });
}

export function isFilterActive(filter: DongFilter): boolean {
  return (
    filter.query.trim() !== "" ||
    filter.gu !== null ||
    filter.statuses.length > 0 ||
    filter.tags.length > 0
  );
}

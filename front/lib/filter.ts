import type { DongSummary } from "./types";

export type DongFilter = {
  query: string;
  gu: string | null;
  /** 주의 있음 = true, 주의 없음 = false, 고르지 않음 = null */
  flagged: boolean | null;
  /** ㎡당 매매 중앙가 구간 [min, max]. 만원 단위이고 양 끝을 포함한다 */
  priceBand: [number, number] | null;
  /** 구조 유형 번호 다중 선택 */
  structureTypes: number[];
  tags: string[];
};

export const EMPTY_FILTER: DongFilter = {
  query: "",
  gu: null,
  flagged: null,
  priceBand: null,
  structureTypes: [],
  tags: [],
};

/** 검색어는 동 이름과 자치구 이름 모두에 걸린다. 선택하지 않은 필터는 조건에서 빠진다. */
export function filterDongs(dongs: DongSummary[], filter: DongFilter): DongSummary[] {
  const query = filter.query.trim();
  return dongs.filter((dong) => {
    if (query && !`${dong.gu_name} ${dong.umd_name}`.includes(query)) return false;
    if (filter.gu && dong.gu_name !== filter.gu) return false;
    if (filter.flagged !== null && dong.sample_flags.length > 0 !== filter.flagged) return false;
    if (filter.priceBand) {
      // 가격을 모르는 동은 구간을 골랐을 때 남기지 않는다. 0으로 보면 가장 싼 구간에 몰린다.
      const price = dong.ppm2_med_4q_manwon;
      if (price === null) return false;
      if (price < filter.priceBand[0] || price > filter.priceBand[1]) return false;
    }
    if (filter.structureTypes.length > 0) {
      if (dong.structure_type === null) return false;
      if (!filter.structureTypes.includes(dong.structure_type)) return false;
    }
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
    filter.flagged !== null ||
    filter.priceBand !== null ||
    filter.structureTypes.length > 0 ||
    filter.tags.length > 0
  );
}

/**
 * 가격대 구간을 전체 분포의 4분위로 만든다(payload-schema.md §3.1).
 * 값이 있는 동만 쓰고, 서로 겹치지 않게 앞 구간의 끝 다음 값부터 다음 구간을 시작한다.
 * 값이 부족해 구간을 나눌 수 없으면 빈 배열이다.
 */
export function priceBandsOf(dongs: DongSummary[]): [number, number][] {
  const prices = dongs
    .map((dong) => dong.ppm2_med_4q_manwon)
    .filter((price): price is number => price !== null && Number.isFinite(price))
    .sort((a, b) => a - b);
  if (prices.length < 4) return [];

  const cut = (ratio: number) => prices[Math.min(prices.length - 1, Math.floor(prices.length * ratio))];
  const edges = [prices[0], cut(0.25), cut(0.5), cut(0.75), prices[prices.length - 1]];
  const bands: [number, number][] = [];
  for (let at = 0; at < 4; at += 1) {
    const from = at === 0 ? edges[0] : edges[at] + 1;
    const to = edges[at + 1];
    if (from <= to) bands.push([from, to]);
  }
  return bands;
}

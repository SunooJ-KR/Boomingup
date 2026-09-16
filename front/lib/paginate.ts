/**
 * 동 목록을 번호로 넘기기 위한 계산. 화면에 들어가는 만큼만 한 페이지에 담는다.
 * 계산만 하고 DOM은 건드리지 않는다.
 */

/** 전체 개수와 한 페이지 크기로 전체 페이지 수를 센다. 항목이 없어도 1페이지는 있다. */
export function pageCount(total: number, size: number): number {
  return Math.max(1, Math.ceil(total / Math.max(1, size)));
}

/** 페이지 번호를 1과 마지막 페이지 사이로 맞춘다. 필터로 목록이 줄어들 때 쓴다. */
export function clampPage(page: number, total: number, size: number): number {
  return Math.min(Math.max(1, page), pageCount(total, size));
}

/**
 * 페이지 버튼에 찍을 번호를 만든다. 처음과 마지막은 항상 넣고,
 * 현재 페이지 앞뒤 span개를 넣은 뒤 끊기는 자리에 "gap"을 넣는다.
 * 예: pageWindow(6, 35) -> [1, "gap", 4, 5, 6, 7, 8, "gap", 35]
 */
export function pageWindow(current: number, total: number, span = 2): (number | "gap")[] {
  if (total < 1) return [];
  const picked = new Set<number>([1, total]);
  for (let page = current - span; page <= current + span; page += 1) {
    if (page >= 1 && page <= total) picked.add(page);
  }

  const sorted = [...picked].sort((a, b) => a - b);
  const result: (number | "gap")[] = [];
  sorted.forEach((page, at) => {
    const previous = sorted[at - 1];
    if (previous !== undefined && page - previous > 1) result.push("gap");
    result.push(page);
  });
  return result;
}

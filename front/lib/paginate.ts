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

/**
 * 목록 칸 높이에 몇 개가 들어가는지 센다. 항목마다 태그 줄 수가 달라 높이가 제각각이라
 * 평균 높이로 어림하고, 남는 자리는 목록 칸 안에서 조금 스크롤된다.
 * min은 화면이 낮아도 목록처럼 보이는 최소 개수, max는 한 번에 너무 많이 그리지 않으려는 상한이다.
 *
 * min이 크면 낮은 화면에서 들어가지도 않는 개수를 목록 칸에 밀어 넣어, 칸 안에서 또 스크롤하게 된다.
 * 좌측 열 자체도 넘칠 때 스크롤되므로 스크롤이 두 겹이 된다. 그래서 min을 낮게 잡는다.
 */
export function fitPageSize(boxHeight: number, itemHeight: number, min = 4, max = 24): number {
  if (!(boxHeight > 0) || !(itemHeight > 0)) return min;
  return Math.min(max, Math.max(min, Math.floor(boxHeight / itemHeight)));
}

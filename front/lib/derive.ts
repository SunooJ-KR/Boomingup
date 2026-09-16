import type { PredictionStatus } from "./types";

/** 모델 출력 log 변화율을 퍼센트로 바꾼다. 소수 1자리로 맞춘다. */
export function logChangeToPct(logChange: number | null | undefined): number | null {
  if (logChange === null || logChange === undefined || !Number.isFinite(logChange)) return null;
  return Math.round((Math.exp(logChange) - 1) * 1000) / 10;
}

/**
 * 예측 상태를 정한다.
 * 예측 행이 있으면 그 값을 쓰고, 없으면 직전 4분기 매매가 기준(결정 7)에 못 미치는지로 나눈다.
 * 기준은 넘었는데 예측이 없으면 모델이 값을 내지 않은 경우이므로 NOT_SERVED로 본다.
 */
export function deriveStatus(
  predictionStatus: string | null | undefined,
  eligible: boolean | null | undefined,
): PredictionStatus {
  if (
    predictionStatus === "PREDICTED" ||
    predictionStatus === "INSUFFICIENT_SALES" ||
    predictionStatus === "NOT_SERVED"
  ) {
    return predictionStatus;
  }
  return eligible ? "NOT_SERVED" : "INSUFFICIENT_SALES";
}

export type TagInput = {
  n_sales_4q: number | null;
  jeonse_ratio_4q: number | null;
  completed_share_8q: number | null;
  old30_share_4q: number | null;
  redevelop_zone_count: number;
};

/** 상위 몇 %를 태그로 볼지. docs/front/product-plan.md §4.3의 "상위 30%"를 따른다. */
const TOP_SHARE = 0.3;

/**
 * 규칙 기반 지역 태그. 좋고 나쁨이 아니라 관측된 특징만 붙인다.
 * 기준값은 서비스 대상 동 전체의 분포에서 정하므로 동 하나만 보고는 만들 수 없다.
 */
export function buildTags(inputs: TagInput[]): string[][] {
  const salesCut = topThreshold(inputs.map((row) => row.n_sales_4q));
  const jeonseCut = topThreshold(inputs.map((row) => row.jeonse_ratio_4q));
  const completedCut = topThreshold(inputs.map((row) => row.completed_share_8q));
  const oldCut = topThreshold(inputs.map((row) => row.old30_share_4q));

  return inputs.map((row) => {
    const tags: string[] = [];
    if (row.redevelop_zone_count > 0) tags.push("정비사업 정보 있음");
    if (overCut(row.n_sales_4q, salesCut)) tags.push("거래 많은 동");
    if (overCut(row.jeonse_ratio_4q, jeonseCut)) tags.push("전세가율 높은 동");
    if (overCut(row.completed_share_8q, completedCut)) tags.push("최근 준공 많은 동");
    if (overCut(row.old30_share_4q, oldCut)) tags.push("30년 이상 단지 많은 동");
    return tags;
  });
}

/** 값이 있는 동만 모아 상위 TOP_SHARE 경계값을 구한다. 쓸 값이 없으면 null */
function topThreshold(values: (number | null)[]): number | null {
  const sorted = values
    .filter((value): value is number => value !== null && Number.isFinite(value) && value > 0)
    .sort((a, b) => b - a);
  if (sorted.length === 0) return null;
  const index = Math.max(0, Math.ceil(sorted.length * TOP_SHARE) - 1);
  return sorted[index];
}

function overCut(value: number | null, cut: number | null): boolean {
  return cut !== null && value !== null && value > 0 && value >= cut;
}

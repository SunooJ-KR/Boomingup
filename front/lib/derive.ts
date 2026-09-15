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
  jeonse_ratio_4q: number | null;
  old30_share_4q: number | null;
  completed_share_8q: number | null;
  redevelop_zone_count: number;
};

/**
 * 규칙 기반 지역 태그. 좋고 나쁨이 아니라 관측된 특징만 붙인다.
 * 임계값은 화면에서 바로 읽히는 수준으로 잡았고, 바뀌면 이 함수만 고친다.
 */
export function deriveTags(input: TagInput): string[] {
  const tags: string[] = [];
  if (input.redevelop_zone_count > 0) tags.push("정비사업 진행");
  if ((input.jeonse_ratio_4q ?? 0) >= 0.6) tags.push("전세 비중 높음");
  if ((input.old30_share_4q ?? 0) >= 0.5) tags.push("노후 단지 비중 높음");
  if ((input.completed_share_8q ?? 0) >= 0.03) tags.push("최근 입주 많음");
  return tags;
}

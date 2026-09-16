import type { Meta, PredictionStatus } from "./types";

const STATUS_LABEL: Record<PredictionStatus, string> = {
  PREDICTED: "예측 있음",
  INSUFFICIENT_SALES: "매매 적음",
  NOT_SERVED: "예측 없음",
};

const STATUS_REASON: Record<PredictionStatus, string> = {
  PREDICTED: "",
  // 목록 카드에서는 옆에 매매 건수가 함께 보이므로 기간을 다시 적지 않는다
  INSUFFICIENT_SALES: "매매가 적어서 예측하지 않았어요",
  NOT_SERVED: "검증 기준을 넘지 못해서 예측하지 않았어요",
};

export function statusLabel(status: PredictionStatus) {
  return STATUS_LABEL[status];
}

export function statusReason(status: PredictionStatus, reason?: string | null) {
  return reason ?? STATUS_REASON[status];
}

/** 변화율은 항상 부호를 붙여 보여준다. 값이 없으면 "-" */
export function formatPct(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

/** "추정 구간 -4.1% ~ +10.9%, 기준 2026년 2분기" */
export function formatInterval(
  lower: number | null | undefined,
  upper: number | null | undefined,
  asOfQuarter: string,
) {
  if (lower === null || lower === undefined || upper === null || upper === undefined) return null;
  return `추정 구간 ${formatPct(lower)} ~ ${formatPct(upper)}, 기준 ${formatQuarter(asOfQuarter)}`;
}

/** "2026Q2" -> "2026년 2분기" */
export function formatQuarter(quarter: string) {
  const match = /^(\d{4})Q([1-4])$/.exec(quarter);
  if (!match) return quarter;
  return `${match[1]}년 ${match[2]}분기`;
}

export function formatHorizon(meta: Meta) {
  return `앞으로 ${meta.horizon_months}개월 추정 변화율`;
}

/** coverage는 반올림한 정수 퍼센트로 안내한다 */
export function formatCoverage(meta: Meta) {
  const pct = Math.round(meta.interval_coverage_backtest * 100);
  return `지난 검증에서 실제 변화율이 추정 구간 안에 든 비율은 약 ${pct}%예요. 시장 흐름이 바뀌는 시기에는 더 낮았어요.`;
}

export function formatManwon(price: number | null | undefined) {
  if (price === null || price === undefined) return "-";
  if (price < 10000) return `${price.toLocaleString("ko-KR")}만원`;
  const eok = Math.floor(price / 10000);
  const rest = price % 10000;
  return rest === 0 ? `${eok}억원` : `${eok}억 ${rest.toLocaleString("ko-KR")}만원`;
}

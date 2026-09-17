// 화면 문구는 docs/wording-guide.md가 정본이다. §3의 문장을 글자 그대로 옮긴다.
// 여기서 임의로 다듬지 않는다. 새 문장이 필요하면 그 문서에 먼저 추가한다.
import type { DeltaState, IndexSeBand, Meta, PeakState, SampleFlag } from "./types";

/** 상세 화면 표본 상태 블록. flag가 여럿이면 이 순서대로 줄을 나눠 전부 보여 준다 */
export const SAMPLE_FLAG_ORDER: SampleFlag[] = [
  "FEW_SALES",
  "ONE_COMPLEX_DOMINATES",
  "HIGH_INDEX_ERROR",
];

const SAMPLE_FLAG_SENTENCE: Record<SampleFlag, string> = {
  FEW_SALES: "최근 1년 매매가 적어 변화율 오차가 커요",
  ONE_COMPLEX_DOMINATES: "최근 거래의 절반 이상이 한 단지에서 나왔어요",
  HIGH_INDEX_ERROR: "지수 추정오차가 커서 작은 변화는 읽지 않는 게 좋아요",
};

const SAMPLE_FLAG_BADGE: Record<SampleFlag, string> = {
  FEW_SALES: "매매 적음",
  ONE_COMPLEX_DOMINATES: "한 단지 쏠림",
  HIGH_INDEX_ERROR: "오차 큼",
};

const INDEX_SE_BAND_SENTENCE: Record<IndexSeBand, string> = {
  LOW: "지수 추정오차 낮음",
  MID: "지수 추정오차 보통",
  HIGH: "지수 추정오차 높음",
};

/**
 * flag가 없으면 아무 문장도 내지 않는다. "주의 없음"이라고 쓰지 않는다.
 * 없음을 좋음으로 읽기 때문이다.
 */
export function sampleFlagSentences(flags: SampleFlag[]): string[] {
  return SAMPLE_FLAG_ORDER.filter((flag) => flags.includes(flag)).map(
    (flag) => SAMPLE_FLAG_SENTENCE[flag],
  );
}

export function sampleFlagBadges(flags: SampleFlag[]): string[] {
  return SAMPLE_FLAG_ORDER.filter((flag) => flags.includes(flag)).map(
    (flag) => SAMPLE_FLAG_BADGE[flag],
  );
}

/** 오차가 낮은 이유가 거래가 많아서라는 것이 보이도록 화면에서는 매매 건수를 옆에 같이 둔다 */
export function indexSeBandSentence(band: IndexSeBand | null): string | null {
  return band === null ? null : INDEX_SE_BAND_SENTENCE[band];
}

/** "지난 12개월 변화 +15.7% · 서울 12.7%" */
export function changeHeadline(dongPct: number | null, seoulPct: number | null): string {
  return `지난 12개월 변화 ${formatPct(dongPct)} · 서울 ${formatPct(seoulPct)}`;
}

/** 서울 평균과의 차이. 구분되지 않으면 값 대신 그렇다고 적는다 */
export function deltaSentence(
  state: DeltaState | null,
  deltaPct: number | null,
  sePct: number | null,
): string | null {
  if (state === null) return null;
  if (state === "INDISTINGUISHABLE") {
    return `서울 평균과 구분되지 않아요 (오차 ±${formatAbsPct(sePct)})`;
  }
  return `서울 평균과 차이 ${formatPct(deltaPct)} (오차 ±${formatAbsPct(sePct)})`;
}

/** 5년 최고 대비 위치. 저거래 동은 state가 없고 그때는 줄을 통째로 뺀다 */
export function peakSentence(
  state: PeakState | null,
  gapPct: number | null,
  sePct: number | null,
): string | null {
  if (state === null) return null;
  if (state === "AT_PEAK") return "최근 5년 중 지금이 지수 최고예요";
  if (state === "INDISTINGUISHABLE") {
    return `5년 최고와 구분되지 않아요 (오차 ±${formatAbsPct(sePct)})`;
  }
  return `5년 최고 대비 ${formatPct(gapPct)} (오차 ±${formatAbsPct(sePct)})`;
}

/** 접힘 블록으로 두는 서울 전체 참고치. 앞날의 값이 아니라 지나간 기간의 평균이다 */
export function referenceSentence(seoulPct: number | null): string {
  return `지난 12개월 서울 아파트 지수 변화 ${formatPct(seoulPct)}. 지나간 기간의 평균이에요.`;
}

/** 화면에 고정으로 붙는 각주. docs/wording-guide.md §6 */
export const FOOTNOTES = {
  change: "변화율은 동 가격 지수 기준이에요. 서울 평균 자체의 오차는 표시하지 않아요.",
  peak: "동 가격 지수 기준이에요. 단지별 신고가와 달라요.",
  redevelop: "2026년 6월 자료예요. 해제·완료된 구역은 반영되지 않았어요.",
  map: "색은 표본 상태와 구조 유형이에요. 변화율이 아니에요.",
  fallback: "샘플 데이터예요. 실제 수치가 아니에요.",
  service: "이 화면은 지나간 거래를 정리한 것이고, 매수·매도 판단을 대신하지 않아요.",
} as const;

export function sampleFootnote(meta: Meta): string {
  return `최근 1년은 ${meta.as_of_quarter} 기준 직전 4분기예요.`;
}

export function structureFootnote(meta: Meta): string {
  return `가격·전세가율·세대수·신축·위치가 비슷한 동끼리 묶은 결과예요. ${meta.cluster_as_of} 기준이고 시장 상황에 따라 바뀔 수 있어요.`;
}

/** 변화율은 항상 부호를 붙여 보여준다. 값이 없으면 "-" */
export function formatPct(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

/** 오차 폭처럼 부호가 뜻이 없는 값은 부호 없이 적는다 */
export function formatAbsPct(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${Math.abs(value).toFixed(1)}%`;
}

/** 0~1 비중을 정수 퍼센트로. 값이 없으면 "-" */
export function formatShare(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${Math.round(value * 100)}%`;
}

/** "2026Q2" -> "2026년 2분기" */
export function formatQuarter(quarter: string) {
  const match = /^(\d{4})Q([1-4])$/.exec(quarter);
  if (!match) return quarter;
  return `${match[1]}년 ${match[2]}분기`;
}

export function formatManwon(price: number | null | undefined) {
  if (price === null || price === undefined) return "-";
  if (price < 10000) return `${price.toLocaleString("ko-KR")}만원`;
  const eok = Math.floor(price / 10000);
  const rest = price % 10000;
  return rest === 0 ? `${eok}억원` : `${eok}억 ${rest.toLocaleString("ko-KR")}만원`;
}

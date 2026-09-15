// docs/payload-schema.md 초안을 따른다.
// tags, status_reason, comparison은 docs/front/frontend-development-plan.md의 추가 후보이며 아직 합의 전이라 optional로 둔다.

export type PredictionStatus = "PREDICTED" | "INSUFFICIENT_SALES" | "NOT_SERVED";

export type DongSummary = {
  dong_id: string;
  sgg_cd: string;
  gu_name: string;
  umd_name: string;
  status: PredictionStatus;
  change_pct_est: number | null;
  lower_pct: number | null;
  upper_pct: number | null;
  n_sales_4q: number;
  tags?: string[];
  status_reason?: string | null;
};

export type Prediction = {
  status: PredictionStatus;
  change_pct_est: number | null;
  lower_pct: number | null;
  upper_pct: number | null;
};

export type DongFacts = {
  n_sales_4q: number;
  jeonse_ratio_4q: number | null;
  redevelop_zones: {
    designated: number;
    association: number;
    management: number;
    construction: number;
  } | null;
  completed_households_8q: number | null;
  reg_overheated: boolean | null;
};

export type DongComparison = {
  seoul_change_pct: number | null;
  gu_change_pct: number | null;
  dong_change_pct: number | null;
};

export type Complex = {
  apt_seq: string;
  name: string;
  built_year: number | null;
  households: number | null;
  far_pct: number | null;
  redevelop: { zone_name: string; stage: string; stage_date: string } | null;
  last_sale: {
    date: string;
    floor: number | null;
    area_m2: number | null;
    price_manwon: number | null;
  } | null;
};

/** 면적대별 과거 실적 조회 결과. 예측이 아니라 지나간 거래를 모은 값이다. */
export type AreaStat = {
  band: string;
  n_sales: number;
  median_price_manwon: number | null;
  min_price_manwon: number | null;
  max_price_manwon: number | null;
};

export type DongDetail = {
  dong_id: string;
  prediction: Prediction;
  facts: DongFacts;
  comparison?: DongComparison;
  area_stats?: AreaStat[];
  /** 면적대 실적을 집계한 기간 (예: "2024-09 ~ 2026-08") */
  area_stats_period?: string;
  complexes: Complex[];
};

export type Meta = {
  as_of_quarter: string;
  data_period: { sale: string; rent: string };
  horizon_months: number;
  model_passed: boolean;
  interval_coverage_backtest: number;
  regulation_as_of: string;
  /** 서울 전체 아파트 토지거래허가구역 지정 여부 */
  seoul_apartment_permit_zone: boolean;
};

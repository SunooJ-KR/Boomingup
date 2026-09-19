// docs/payload-schema.md v2를 따른다. 필드 이름은 docs/feature-spec.md §5의 컬럼명과 같다.
// 앞날을 추정하는 필드는 없다. 화면에 판단 표현이 들어오지 않도록 응답 구조에서부터 막는다(결정 66).

export type SampleFlag = "FEW_SALES" | "ONE_COMPLEX_DOMINATES" | "HIGH_INDEX_ERROR";

export type IndexSeBand = "LOW" | "MID" | "HIGH";

export type DeltaState = "DISTINGUISHABLE" | "INDISTINGUISHABLE";

export type PeakState = "AT_PEAK" | "DISTINGUISHABLE" | "INDISTINGUISHABLE";

export type DongSummary = {
  dong_id: string;
  sgg_cd: string;
  gu_name: string;
  umd_name: string;
  n_sales_4q: number;
  /** 최근 4분기 ㎡당 매매 중앙가(만원). 가격대 필터와 정렬에 쓴다 */
  ppm2_med_4q_manwon: number | null;
  sample_flags: SampleFlag[];
  index_se_band: IndexSeBand | null;
  structure_type: number | null;
  structure_desc: string | null;
  tags?: string[];
  /** 지역 특성 정렬에 쓰는 원래 관측값 */
  tag_sort_values?: Record<string, number | null>;
};

/** 표본 상태. 이 값이 없으면 변화율을 읽는 기준도 없다 */
export type DongSample = {
  n_sales_4q: number;
  n_complexes_4q: number | null;
  /** 매매 0건이면 낼 수 없어 null이다. 0으로 채우지 않는다 */
  dominant_complex_share_4q: number | null;
  index_se: number | null;
  index_se_band: IndexSeBand | null;
  flags: SampleFlag[];
};

/**
 * 지난 12개월 변화와 5년 범위 위치. 모두 %로 바꾼 값이다.
 * delta_state가 INDISTINGUISHABLE이면 delta_12m_pct는 서버가 null로 지운다.
 * peak_5y_*도 같은 규칙이고, 5년 창이 짧은 동은 셋 다 null이다.
 */
export type DongChange = {
  dong_12m_pct: number | null;
  seoul_12m_pct: number | null;
  delta_12m_pct: number | null;
  delta_se_pct: number | null;
  delta_state: DeltaState | null;
  peak_5y_gap_pct: number | null;
  peak_5y_gap_se_pct: number | null;
  peak_5y_state: PeakState | null;
};

/** 분기별 거래 흐름. dong_support에 없고 API가 거래 원장에서 집계한다 */
export type DongFlow = {
  quarter: string;
  n_sales: number;
  n_jeonse: number;
  monthly_rent_share: number | null;
};

export type DongStructure = {
  type: number;
  desc: string;
  as_of: string;
};

export type DongPeer = {
  dong_id: string;
  gu_name: string;
  umd_name: string;
  reason: string;
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

/** 면적대별 매매 가격 분포. 지나간 거래를 모은 값이다 */
export type AreaStat = {
  band: string;
  n_sales: number;
  median_price_manwon: number | null;
  min_price_manwon: number | null;
  max_price_manwon: number | null;
};

export type DongDetail = {
  dong_id: string;
  sample: DongSample;
  change: DongChange;
  flows: DongFlow[];
  facts: DongFacts;
  /** 구조 유형이 없는 동은 null이다 */
  structure: DongStructure | null;
  /** 표시 조건을 못 채우면 null이다. 빈 배열이 아니다. null이면 블록을 그리지 않는다 */
  peers: DongPeer[] | null;
  reference: { seoul_12m_pct: number | null };
  area_stats?: AreaStat[];
  /** 면적대 가격 분포를 집계한 기간 (예: "2024-09 ~ 2026-08") */
  area_stats_period?: string;
  complexes: Complex[];
};

/** 화면 각주에 쓰는 문턱값. docs/feature-spec.md §1.5·§2.5 */
export type Thresholds = {
  few_sales: number;
  one_complex_share: number;
  high_index_se: number;
  delta_sigma: number;
};

export type Meta = {
  as_of_quarter: string;
  data_period: { sale: string; rent: string };
  /** dong_support의 as_of */
  support_as_of: string;
  /** 구조 유형을 정한 기점 */
  cluster_as_of: string;
  thresholds: Thresholds;
  regulation_as_of: string;
  /** 서울 전체 아파트 토지거래허가구역 지정 여부 */
  seoul_apartment_permit_zone: boolean;
};

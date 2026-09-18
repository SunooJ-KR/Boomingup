import "server-only";

import { query } from "./db";
import { buildTags, logChangeToPct, logSeToPct } from "./derive";
import { parseQuarter, shiftQuarter } from "./quarter";
import type {
  AreaStat,
  Complex,
  DeltaState,
  DongDetail,
  DongFlow,
  DongPeer,
  DongSummary,
  IndexSeBand,
  Meta,
  PeakState,
  SampleFlag,
  Thresholds,
} from "./types";

/**
 * active snapshot만 읽는다. snapshot_id를 코드에 박지 않는다.
 * docs/railway-postgres-onboarding.md §5의 규칙을 그대로 따른다.
 */
const ACTIVE_SNAPSHOT = "(select snapshot_id from app.dataset_snapshot where is_active limit 1)";
const ACTIVE_SALE_BATCH =
  "(select batch_id from app.trade_batch where kind = 'sale' and is_active limit 1)";
const ACTIVE_RENT_BATCH =
  "(select batch_id from app.trade_batch where kind = 'rent' and is_active limit 1)";

/**
 * 화면 각주에 그대로 적는 문턱값이다. docs/feature-spec.md §1.5·§2.5에서 정했다.
 * 판정 자체는 산출 스크립트가 이미 끝냈고, 여기서는 그 표시가 나온 기준을 적기 위해서만 쓴다.
 */
const THRESHOLDS: Thresholds = {
  few_sales: 20,
  one_complex_share: 0.5,
  high_index_se: 0.032,
  delta_sigma: 2,
};

/** 거래 흐름 블록이 보여주는 분기 수 */
const FLOW_QUARTERS = 8;

export async function fetchMeta(): Promise<Meta> {
  const [quarterRow] = await query<{ as_of_quarter: string }>(
    `select max(quarter) as as_of_quarter from app.dong_index where snapshot_id = ${ACTIVE_SNAPSHOT}`,
  );
  const [supportRow] = await query<{ support_as_of: string | null }>(
    `select max(as_of) as support_as_of from app.dong_support where snapshot_id = ${ACTIVE_SNAPSHOT}`,
  );
  const batches = await query<{ kind: string; period_start: string; period_end: string }>(
    "select kind, period_start, period_end from app.trade_batch where is_active",
  );
  const [regulation] = await query<{
    as_of: Date | string | null;
    seoul_apartment_permit_zone: boolean | null;
  }>(
    `select as_of, seoul_apartment_permit_zone
       from app.regulation_summary where snapshot_id = ${ACTIVE_SNAPSHOT} limit 1`,
  );

  const period = (kind: string) => {
    const batch = batches.find((row) => row.kind === kind);
    return batch ? `${formatYm(batch.period_start)} ~ ${formatYm(batch.period_end)}` : "-";
  };

  const supportAsOf = supportRow?.support_as_of ?? "-";

  return {
    as_of_quarter: quarterRow?.as_of_quarter ?? "-",
    data_period: { sale: period("sale"), rent: period("rent") },
    support_as_of: supportAsOf,
    // 산출 스크립트가 66.1의 소속을 기준 분기 T로 걸러 쓰므로 구조 유형 기점은 항상 support와 같다.
    cluster_as_of: supportAsOf,
    thresholds: THRESHOLDS,
    regulation_as_of: toDateString(regulation?.as_of) ?? "-",
    seoul_apartment_permit_zone: regulation?.seoul_apartment_permit_zone ?? false,
  };
}

type DongRow = {
  dong: string;
  sgg_cd: string;
  umd_nm: string;
  gu_name: string;
  n_sales_4q: number | null;
  sale_n_all_4q: number | null;
  sale_ppm2_med_4q: number | string | null;
  sample_flags: string | null;
  index_se_band: string | null;
  structure_type: number | null;
  structure_desc: string | null;
  jeonse_ratio_4q: number | null;
  old30_share_4q: number | null;
  completed_share_8q: number | null;
  redevelop_zone_count: number | null;
};

export async function fetchDongs(asOfQuarter: string): Promise<DongSummary[]> {
  const rows = await query<DongRow>(
    `select d.dong, d.sgg_cd, d.umd_nm, d.gu_name,
            i.n_sales_4q,
            s.sale_n_all_4q, s.sample_flags, s.index_se_band, s.structure_type, s.structure_desc,
            f.sale_ppm2_med_4q, f.jeonse_ratio_4q, f.old30_share_4q, f.completed_share_8q,
            coalesce(f.rz_designated_n, 0) + coalesce(f.rz_association_n, 0)
              + coalesce(f.rz_management_n, 0) + coalesce(f.rz_construction_n, 0) as redevelop_zone_count
       from app.dong d
       join app.dong_index i
         on i.snapshot_id = d.snapshot_id and i.dong = d.dong and i.quarter = $1
       left join app.dong_feature f
         on f.snapshot_id = d.snapshot_id and f.dong = d.dong and f.as_of_quarter = $1
       left join app.dong_support s
         on s.snapshot_id = d.snapshot_id and s.dong = d.dong
      where d.snapshot_id = ${ACTIVE_SNAPSHOT}
      order by d.gu_name, d.umd_nm`,
    [asOfQuarter],
  );

  // 태그는 서비스 대상 동 전체 분포에서 정하므로 목록을 다 읽은 뒤에 붙인다
  const tags = buildTags(
    rows.map((row) => ({
      n_sales_4q: row.n_sales_4q,
      jeonse_ratio_4q: numberOrNull(row.jeonse_ratio_4q),
      completed_share_8q: numberOrNull(row.completed_share_8q),
      old30_share_4q: numberOrNull(row.old30_share_4q),
      redevelop_zone_count: Number(row.redevelop_zone_count ?? 0),
    })),
  );

  return rows.map((row, at) => ({
    dong_id: row.dong,
    sgg_cd: row.sgg_cd,
    gu_name: row.gu_name,
    umd_name: row.umd_nm,
    // 표본 주의 flag를 이 건수로 판정했으므로 화면에도 같은 값을 보여준다.
    n_sales_4q: row.sale_n_all_4q ?? row.n_sales_4q ?? 0,
    ppm2_med_4q_manwon: roundOrNull(row.sale_ppm2_med_4q),
    sample_flags: parseSampleFlags(row.sample_flags),
    index_se_band: asIndexSeBand(row.index_se_band),
    structure_type: row.structure_type ?? null,
    structure_desc: row.structure_desc ?? null,
    tags: tags[at],
    tag_sort_values: {
      "정비사업 정보 있음": numberOrNull(row.redevelop_zone_count),
      "거래 많은 동": numberOrNull(row.n_sales_4q),
      "전세가율 높은 동": numberOrNull(row.jeonse_ratio_4q),
      "최근 준공 많은 동": numberOrNull(row.completed_share_8q),
      "30년 이상 단지 많은 동": numberOrNull(row.old30_share_4q),
    },
  }));
}

type DetailRow = {
  dong: string;
  gu_name: string;
  n_sales_4q: number | null;
  sale_n_all_4q: number | null;
  n_complexes_4q: number | null;
  dominant_complex_share_4q: number | string | null;
  index_se: number | string | null;
  index_se_band: string | null;
  sample_flags: string | null;
  change_12m: number | string | null;
  mu_12m: number | string | null;
  delta_12m: number | string | null;
  delta_se: number | string | null;
  delta_state: string | null;
  peak_5y_gap: number | string | null;
  peak_5y_gap_se: number | string | null;
  peak_5y_state: string | null;
  structure_type: number | null;
  structure_desc: string | null;
  support_as_of: string;
  peer_dongs: { dong: string; reason: string }[] | null;
  jeonse_ratio_4q: number | null;
  completed_hh_8q: number | null;
  rz_designated_n: number | null;
  rz_association_n: number | null;
  rz_management_n: number | null;
  rz_construction_n: number | null;
};

export async function fetchDongDetail(
  dongId: string,
  asOfQuarter: string,
): Promise<DongDetail | null> {
  const [sggCd, umdNm] = splitDongId(dongId);
  if (!sggCd || !umdNm) return null;

  // 상세 화면의 다섯 블록이 모두 dong_support 값을 쓴다. 그 행이 없으면 그릴 화면이 없다.
  const [row] = await query<DetailRow>(
    `select d.dong, d.gu_name, i.n_sales_4q,
            s.sale_n_all_4q, s.n_complexes_4q, s.dominant_complex_share_4q,
            s.index_se, s.index_se_band, s.sample_flags,
            s.change_12m, s.mu_12m, s.delta_12m, s.delta_se, s.delta_state,
            s.peak_5y_gap, s.peak_5y_gap_se, s.peak_5y_state,
            s.structure_type, s.structure_desc, s.as_of as support_as_of, s.peer_dongs,
            f.jeonse_ratio_4q, f.completed_hh_8q,
            f.rz_designated_n, f.rz_association_n, f.rz_management_n, f.rz_construction_n
       from app.dong d
       join app.dong_support s
         on s.snapshot_id = d.snapshot_id and s.dong = d.dong
       left join app.dong_index i
         on i.snapshot_id = d.snapshot_id and i.dong = d.dong and i.quarter = $2
       left join app.dong_feature f
         on f.snapshot_id = d.snapshot_id and f.dong = d.dong and f.as_of_quarter = $2
      where d.snapshot_id = ${ACTIVE_SNAPSHOT} and d.dong = $1`,
    [dongId, asOfQuarter],
  );
  if (!row) return null;

  const [complexes, areaStats, flows, peers] = await Promise.all([
    fetchComplexes(sggCd, umdNm),
    fetchAreaStats(sggCd, umdNm),
    fetchFlows(sggCd, umdNm, asOfQuarter),
    fetchPeers(row.peer_dongs),
  ]);

  const deltaState = asDeltaState(row.delta_state);
  const peakState = asPeakState(row.peak_5y_state);
  const seoul12mPct = logChangeToPct(numberOrNull(row.mu_12m));

  return {
    dong_id: row.dong,
    sample: {
      n_sales_4q: row.sale_n_all_4q ?? row.n_sales_4q ?? 0,
      n_complexes_4q: row.n_complexes_4q ?? null,
      dominant_complex_share_4q: numberOrNull(row.dominant_complex_share_4q),
      index_se: numberOrNull(row.index_se),
      index_se_band: asIndexSeBand(row.index_se_band),
      flags: parseSampleFlags(row.sample_flags),
    },
    change: {
      dong_12m_pct: logChangeToPct(numberOrNull(row.change_12m)),
      seoul_12m_pct: seoul12mPct,
      // 서울 평균과 구분되지 않는 차이는 서버에서 지운다. 프론트가 숨기는 것이 아니다.
      delta_12m_pct:
        deltaState === "DISTINGUISHABLE" ? logChangeToPct(numberOrNull(row.delta_12m)) : null,
      delta_se_pct: logSeToPct(numberOrNull(row.delta_12m), numberOrNull(row.delta_se)),
      delta_state: deltaState,
      peak_5y_gap_pct:
        peakState === null || peakState === "INDISTINGUISHABLE"
          ? null
          : logChangeToPct(numberOrNull(row.peak_5y_gap)),
      peak_5y_gap_se_pct: logSeToPct(
        numberOrNull(row.peak_5y_gap),
        numberOrNull(row.peak_5y_gap_se),
      ),
      peak_5y_state: peakState,
    },
    flows,
    facts: {
      n_sales_4q: row.sale_n_all_4q ?? row.n_sales_4q ?? 0,
      jeonse_ratio_4q: numberOrNull(row.jeonse_ratio_4q),
      redevelop_zones: {
        designated: Number(row.rz_designated_n ?? 0),
        association: Number(row.rz_association_n ?? 0),
        management: Number(row.rz_management_n ?? 0),
        construction: Number(row.rz_construction_n ?? 0),
      },
      completed_households_8q: numberOrNull(row.completed_hh_8q),
      reg_overheated: null,
    },
    structure:
      row.structure_type === null || row.structure_desc === null
        ? null
        : { type: row.structure_type, desc: row.structure_desc, as_of: row.support_as_of },
    peers,
    reference: { seoul_12m_pct: seoul12mPct },
    area_stats: areaStats.bands,
    area_stats_period: areaStats.period,
    complexes,
  };
}

/**
 * 함께 볼 동의 이름을 붙인다. dong_support에는 동 코드와 이유만 있다.
 * 표시 조건을 못 채운 동은 peer_dongs가 비어 있고, 그때는 블록을 아예 그리지 않도록 null을 돌려준다.
 */
async function fetchPeers(
  peerDongs: { dong: string; reason: string }[] | null,
): Promise<DongPeer[] | null> {
  if (!peerDongs || peerDongs.length === 0) return null;
  const rows = await query<{ dong: string; gu_name: string; umd_nm: string }>(
    `select dong, gu_name, umd_nm
       from app.dong
      where snapshot_id = ${ACTIVE_SNAPSHOT} and dong = any($1)`,
    [peerDongs.map((peer) => peer.dong)],
  );
  const names = new Map(rows.map((row) => [row.dong, row]));

  return peerDongs.flatMap((peer) => {
    const name = names.get(peer.dong);
    if (!name) return [];
    return [
      { dong_id: peer.dong, gu_name: name.gu_name, umd_name: name.umd_nm, reason: peer.reason },
    ];
  });
}

/** "202608" -> "2026Q3". deal_ym이 'YYYYMM' 문자열이라 SQL에서 분기로 접는다. */
const QUARTER_OF_YM =
  "substr(t.deal_ym, 1, 4) || 'Q' || ((cast(substr(t.deal_ym, 5, 2) as int) + 2) / 3)";

/**
 * 최근 8분기 거래 흐름. dong_support에 없어서 거래 원장에서 직접 센다.
 * 월세 비중은 건수 기준이다(payload-schema.md §9의 미정 항목). 보증금 환산으로 바꾸려면
 * 그 결정을 문서에 먼저 적는다.
 * 거래가 하나도 없는 분기는 행이 나오지 않으므로 0으로 채워 8분기를 모두 보여준다.
 */
async function fetchFlows(sggCd: string, umdNm: string, asOfQuarter: string): Promise<DongFlow[]> {
  const quarters = Array.from({ length: FLOW_QUARTERS }, (_, at) =>
    shiftQuarter(asOfQuarter, at - (FLOW_QUARTERS - 1)),
  );
  const fromYm = quarterFirstYm(quarters[0]);
  const toYm = quarterLastYm(asOfQuarter);
  if (!fromYm || !toYm) return [];

  const rows = await query<{
    quarter: string;
    n_sales: string | null;
    n_rent: string | null;
    n_jeonse: string | null;
    n_monthly: string | null;
  }>(
    `with sales as (
       select ${QUARTER_OF_YM} as quarter, count(*) as n_sales
         from app.trade_sale t
        where t.batch_id = ${ACTIVE_SALE_BATCH}
          and t.sgg_cd = $1 and t.umd_nm = $2 and not t.is_cancelled
          and t.deal_ym between $3 and $4
        group by 1
     ),
     rents as (
       select ${QUARTER_OF_YM} as quarter,
              count(*) as n_rent,
              count(*) filter (where t.is_jeonse) as n_jeonse,
              count(*) filter (where not t.is_jeonse) as n_monthly
         from app.trade_rent t
        where t.batch_id = ${ACTIVE_RENT_BATCH}
          and t.sgg_cd = $1 and t.umd_nm = $2
          and t.deal_ym between $3 and $4
        group by 1
     )
     select coalesce(s.quarter, r.quarter) as quarter,
            s.n_sales, r.n_rent, r.n_jeonse, r.n_monthly
       from sales s
       full join rents r on r.quarter = s.quarter`,
    [sggCd, umdNm, fromYm, toYm],
  );

  const byQuarter = new Map(rows.map((row) => [row.quarter, row]));
  return quarters.map((quarter) => {
    const row = byQuarter.get(quarter);
    const nRent = Number(row?.n_rent ?? 0);
    return {
      quarter,
      n_sales: Number(row?.n_sales ?? 0),
      n_jeonse: Number(row?.n_jeonse ?? 0),
      // 전월세 거래가 없는 분기는 비중을 0이 아니라 없음으로 둔다.
      monthly_rent_share: nRent > 0 ? Number(row?.n_monthly ?? 0) / nRent : null,
    };
  });
}

function quarterFirstYm(quarter: string): string | null {
  const parsed = parseQuarter(quarter);
  if (!parsed) return null;
  return `${parsed.year}${String((parsed.q - 1) * 3 + 1).padStart(2, "0")}`;
}

function quarterLastYm(quarter: string): string | null {
  const parsed = parseQuarter(quarter);
  if (!parsed) return null;
  return `${parsed.year}${String(parsed.q * 3).padStart(2, "0")}`;
}

/** 면적대 구분. 전용면적 기준이고, 화면에도 이 이름 그대로 쓴다. */
const AREA_BANDS = ["60㎡ 미만", "60~85㎡", "85~135㎡", "135㎡ 이상"];

/** 최근 24개월 집계 창 */
const AREA_STATS_MONTHS = 24;

/**
 * 면적대별 매매 가격 분포. 지나간 거래를 모은 값이다.
 * 표본이 적은 동에서 중위값이 흔들리므로 거래 수를 항상 같이 돌려준다.
 */
async function fetchAreaStats(
  sggCd: string,
  umdNm: string,
): Promise<{ bands: AreaStat[]; period: string }> {
  const rows = await query<{
    band_no: number;
    n_sales: string;
    median_price_manwon: string | null;
    min_price_manwon: string | null;
    max_price_manwon: string | null;
    from_ym: string;
    to_ym: string;
  }>(
    `with window_ym as (
       select to_char(to_date(period_end, 'YYYYMM') - interval '${AREA_STATS_MONTHS - 1} months', 'YYYYMM') as from_ym,
              period_end as to_ym
         from app.trade_batch
        where batch_id = ${ACTIVE_SALE_BATCH}
     ),
     banded as (
       select case
                when t.exclu_use_ar < 60 then 0
                when t.exclu_use_ar < 85 then 1
                when t.exclu_use_ar < 135 then 2
                else 3
              end as band_no,
              t.deal_amount_manwon
         from app.trade_sale t, window_ym w
        where t.batch_id = ${ACTIVE_SALE_BATCH}
          and t.sgg_cd = $1 and t.umd_nm = $2
          and not t.is_cancelled
          and t.deal_ym >= w.from_ym
     )
     select b.band_no,
            count(*) as n_sales,
            percentile_cont(0.5) within group (order by b.deal_amount_manwon) as median_price_manwon,
            min(b.deal_amount_manwon) as min_price_manwon,
            max(b.deal_amount_manwon) as max_price_manwon,
            w.from_ym, w.to_ym
       from banded b, window_ym w
      group by b.band_no, w.from_ym, w.to_ym
      order by b.band_no`,
    [sggCd, umdNm],
  );

  const period = rows[0] ? `${formatYm(rows[0].from_ym)} ~ ${formatYm(rows[0].to_ym)}` : "-";
  const bands = rows.map((row) => ({
    band: AREA_BANDS[row.band_no] ?? "기타",
    n_sales: Number(row.n_sales),
    median_price_manwon: roundOrNull(row.median_price_manwon),
    min_price_manwon: roundOrNull(row.min_price_manwon),
    max_price_manwon: roundOrNull(row.max_price_manwon),
  }));

  return { bands, period };
}

function roundOrNull(value: string | number | null): number | null {
  const parsed = numberOrNull(value);
  return parsed === null ? null : Math.round(parsed);
}

/**
 * 단지는 app.complex에 법정동 코드가 없어서 매매 기록의 (sgg_cd, umd_nm)으로 묶는다.
 * 그래서 매매 기록이 한 번도 없는 단지는 목록에 나오지 않는다.
 */
async function fetchComplexes(sggCd: string, umdNm: string): Promise<Complex[]> {
  const rows = await query<{
    apt_seq: string;
    name: string;
    built_year: number | null;
    total_households: number | null;
    far: number | null;
    redevelop_type: string | null;
    redevelop_stage: string | null;
    deal_ym: string | null;
    floor: number | null;
    exclu_use_ar: number | null;
    deal_amount_manwon: number | null;
  }>(
    `with last_sale as (
       select distinct on (t.apt_seq)
              t.apt_seq, t.apt_nm, t.deal_ym, t.floor, t.exclu_use_ar, t.deal_amount_manwon
         from app.trade_sale t
        where t.batch_id = ${ACTIVE_SALE_BATCH}
          and t.sgg_cd = $1 and t.umd_nm = $2 and not t.is_cancelled
        order by t.apt_seq, t.deal_ym desc, t.row_no desc
     )
     select ls.apt_seq,
            coalesce(c.name, ls.apt_nm) as name,
            c.built_year, c.total_households, c.far, c.redevelop_type, c.redevelop_stage,
            ls.deal_ym, ls.floor, ls.exclu_use_ar, ls.deal_amount_manwon
       from last_sale ls
       left join app.complex c
         on c.snapshot_id = ${ACTIVE_SNAPSHOT} and c.apt_seq = ls.apt_seq
      order by ls.deal_ym desc, ls.apt_seq
      limit 50`,
    [sggCd, umdNm],
  );

  return rows.map((row) => ({
    apt_seq: row.apt_seq,
    name: row.name,
    built_year: row.built_year,
    households: row.total_households,
    far_pct: numberOrNull(row.far),
    redevelop: row.redevelop_stage
      ? {
          zone_name: row.redevelop_type ?? "정비사업",
          stage: row.redevelop_stage,
          stage_date: "",
        }
      : null,
    last_sale: row.deal_ym
      ? {
          date: formatYm(row.deal_ym),
          floor: row.floor,
          area_m2: numberOrNull(row.exclu_use_ar),
          price_manwon: numberOrNull(row.deal_amount_manwon),
        }
      : null,
  }));
}

/** 지도 마커용 동 대표 좌표. 경계 GeoJSON이 없어 최근 거래 단지 좌표의 평균을 쓴다. */
export async function fetchDongCenters(): Promise<Record<string, { lat: number; lng: number }>> {
  const rows = await query<{ dong: string; lat: number; lng: number }>(
    `with pairs as (
       select distinct t.sgg_cd || '_' || t.umd_nm as dong, t.apt_seq
         from app.trade_sale t
        where t.batch_id = ${ACTIVE_SALE_BATCH} and t.deal_year >= 2020
     )
     select p.dong, avg(c.lat) as lat, avg(c.lng) as lng
       from pairs p
       join app.complex c
         on c.snapshot_id = ${ACTIVE_SNAPSHOT} and c.apt_seq = p.apt_seq and c.lat is not null
      group by p.dong`,
  );

  return Object.fromEntries(
    rows.map((row) => [row.dong, { lat: Number(row.lat), lng: Number(row.lng) }]),
  );
}

const SAMPLE_FLAGS: SampleFlag[] = ["FEW_SALES", "ONE_COMPLEX_DOMINATES", "HIGH_INDEX_ERROR"];

/** ';'로 이어 둔 flag 문자열을 배열로 편다. 없으면 빈 배열이다. */
function parseSampleFlags(value: string | null): SampleFlag[] {
  if (!value) return [];
  return value
    .split(";")
    .map((flag) => flag.trim())
    .filter((flag): flag is SampleFlag => (SAMPLE_FLAGS as string[]).includes(flag));
}

function asIndexSeBand(value: string | null): IndexSeBand | null {
  return value === "LOW" || value === "MID" || value === "HIGH" ? value : null;
}

function asDeltaState(value: string | null): DeltaState | null {
  return value === "DISTINGUISHABLE" || value === "INDISTINGUISHABLE" ? value : null;
}

function asPeakState(value: string | null): PeakState | null {
  return value === "AT_PEAK" || value === "DISTINGUISHABLE" || value === "INDISTINGUISHABLE"
    ? value
    : null;
}

function splitDongId(dongId: string): [string, string] {
  const at = dongId.indexOf("_");
  if (at < 0) return ["", ""];
  return [dongId.slice(0, at), dongId.slice(at + 1)];
}

/** pg는 numeric을 문자열로 돌려준다. 화면에서 계산하기 전에 숫자로 맞춘다. */
function numberOrNull(value: number | string | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** "202608" 또는 "2026-08"을 "2026-08"로 맞춘다 */
function formatYm(value: string): string {
  const digits = value.replace(/\D/g, "");
  return digits.length === 6 ? `${digits.slice(0, 4)}-${digits.slice(4)}` : value;
}

function toDateString(value: Date | string | null | undefined): string | null {
  if (!value) return null;
  return value instanceof Date ? value.toISOString().slice(0, 10) : String(value).slice(0, 10);
}

import "server-only";

import { query } from "./db";
import { buildTags, deriveStatus, logChangeToPct } from "./derive";
import { shiftQuarter } from "./quarter";
import type { Complex, DongDetail, DongSummary, Meta } from "./types";

/**
 * active snapshot만 읽는다. snapshot_id를 코드에 박지 않는다.
 * docs/railway-postgres-onboarding.md §5의 규칙을 그대로 따른다.
 */
const ACTIVE_SNAPSHOT = "(select snapshot_id from app.dataset_snapshot where is_active limit 1)";
const ACTIVE_SALE_BATCH =
  "(select batch_id from app.trade_batch where kind = 'sale' and is_active limit 1)";

/** 12개월 예측(결정 16) = 4분기 */
const HORIZON_QUARTERS = 4;

/**
 * 모델 판정값은 아직 DB에 적재되지 않아 docs/decisions.md 결정 16·17 값을 상수로 둔다.
 * app.dong_prediction이 채워지면 그 행에서 읽도록 바꾼다.
 */
const MODEL_PASSED = true;
const INTERVAL_COVERAGE_BACKTEST = 0.641;

export async function fetchMeta(): Promise<Meta> {
  const [quarterRow] = await query<{ as_of_quarter: string }>(
    `select max(quarter) as as_of_quarter from app.dong_index where snapshot_id = ${ACTIVE_SNAPSHOT}`,
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

  return {
    as_of_quarter: quarterRow?.as_of_quarter ?? "-",
    data_period: { sale: period("sale"), rent: period("rent") },
    horizon_months: HORIZON_QUARTERS * 3,
    model_passed: MODEL_PASSED,
    interval_coverage_backtest: INTERVAL_COVERAGE_BACKTEST,
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
  eligible: boolean | null;
  status: string | null;
  change_pct_est: number | null;
  lower_pct: number | null;
  upper_pct: number | null;
  jeonse_ratio_4q: number | null;
  old30_share_4q: number | null;
  completed_share_8q: number | null;
  redevelop_zone_count: number | null;
};

export async function fetchDongs(asOfQuarter: string): Promise<DongSummary[]> {
  const rows = await query<DongRow>(
    `select d.dong, d.sgg_cd, d.umd_nm, d.gu_name,
            i.n_sales_4q, i.eligible,
            p.status, p.change_pct_est, p.lower_pct, p.upper_pct,
            f.jeonse_ratio_4q, f.old30_share_4q, f.completed_share_8q,
            coalesce(f.rz_designated_n, 0) + coalesce(f.rz_association_n, 0)
              + coalesce(f.rz_management_n, 0) + coalesce(f.rz_construction_n, 0) as redevelop_zone_count
       from app.dong d
       join app.dong_index i
         on i.snapshot_id = d.snapshot_id and i.dong = d.dong and i.quarter = $1
       left join app.dong_feature f
         on f.snapshot_id = d.snapshot_id and f.dong = d.dong and f.as_of_quarter = $1
       left join app.dong_prediction p
         on p.snapshot_id = d.snapshot_id and p.dong = d.dong
        and p.origin = $1 and p.horizon_q = ${HORIZON_QUARTERS}
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
    status: deriveStatus(row.status, row.eligible),
    change_pct_est: numberOrNull(row.change_pct_est),
    lower_pct: numberOrNull(row.lower_pct),
    upper_pct: numberOrNull(row.upper_pct),
    n_sales_4q: row.n_sales_4q ?? 0,
    tags: tags[at],
  }));
}

export async function fetchDongDetail(
  dongId: string,
  asOfQuarter: string,
): Promise<DongDetail | null> {
  const [sggCd, umdNm] = splitDongId(dongId);
  if (!sggCd || !umdNm) return null;
  const baseQuarter = shiftQuarter(asOfQuarter, -HORIZON_QUARTERS);

  const [row] = await query<{
    dong: string;
    gu_name: string;
    eligible: boolean | null;
    n_sales_4q: number | null;
    status: string | null;
    change_pct_est: number | null;
    lower_pct: number | null;
    upper_pct: number | null;
    sale_n_all_4q: number | null;
    jeonse_ratio_4q: number | null;
    completed_hh_8q: number | null;
    rz_designated_n: number | null;
    rz_association_n: number | null;
    rz_management_n: number | null;
    rz_construction_n: number | null;
    dong_log_change: number | null;
  }>(
    `select d.dong, d.gu_name, i.eligible, i.n_sales_4q,
            p.status, p.change_pct_est, p.lower_pct, p.upper_pct,
            f.sale_n_all_4q, f.jeonse_ratio_4q, f.completed_hh_8q,
            f.rz_designated_n, f.rz_association_n, f.rz_management_n, f.rz_construction_n,
            i.log_index - prev.log_index as dong_log_change
       from app.dong d
       join app.dong_index i
         on i.snapshot_id = d.snapshot_id and i.dong = d.dong and i.quarter = $2
       left join app.dong_index prev
         on prev.snapshot_id = d.snapshot_id and prev.dong = d.dong and prev.quarter = $3
       left join app.dong_feature f
         on f.snapshot_id = d.snapshot_id and f.dong = d.dong and f.as_of_quarter = $2
       left join app.dong_prediction p
         on p.snapshot_id = d.snapshot_id and p.dong = d.dong
        and p.origin = $2 and p.horizon_q = ${HORIZON_QUARTERS}
      where d.snapshot_id = ${ACTIVE_SNAPSHOT} and d.dong = $1`,
    [dongId, asOfQuarter, baseQuarter],
  );
  if (!row) return null;

  const [comparison] = await query<{
    seoul_log_change: number | null;
    gu_log_change: number | null;
  }>(
    `with changes as (
       select d.gu_name, i.log_index - prev.log_index as log_change
         from app.dong d
         join app.dong_index i
           on i.snapshot_id = d.snapshot_id and i.dong = d.dong and i.quarter = $2 and i.eligible
         join app.dong_index prev
           on prev.snapshot_id = d.snapshot_id and prev.dong = d.dong and prev.quarter = $3
        where d.snapshot_id = ${ACTIVE_SNAPSHOT}
     )
     select avg(log_change) as seoul_log_change,
            avg(log_change) filter (where gu_name = $1) as gu_log_change
       from changes`,
    [row.gu_name, asOfQuarter, baseQuarter],
  );

  const complexes = await fetchComplexes(sggCd, umdNm);

  return {
    dong_id: row.dong,
    prediction: {
      status: deriveStatus(row.status, row.eligible),
      change_pct_est: numberOrNull(row.change_pct_est),
      lower_pct: numberOrNull(row.lower_pct),
      upper_pct: numberOrNull(row.upper_pct),
    },
    facts: {
      n_sales_4q: row.n_sales_4q ?? row.sale_n_all_4q ?? 0,
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
    comparison: {
      seoul_change_pct: logChangeToPct(numberOrNull(comparison?.seoul_log_change)),
      gu_change_pct: logChangeToPct(numberOrNull(comparison?.gu_log_change)),
      dong_change_pct: logChangeToPct(numberOrNull(row.dong_log_change)),
    },
    complexes,
  };
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

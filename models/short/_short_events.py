# ============================================================================
# _short_events.py
# ============================================================================
# Author:      yjkim
# Purpose:     P8이 공유하는 도시철도 exposure와 준공 flow feature를 만든다
# Description: 공개일·publication lag를 origin별로 적용하며 미래 정보 사용을 assert한다.
# ============================================================================

from pathlib import Path

import numpy as np
import pandas as pd

from _short_index import OUTPUT_DIR, mi_to_ym, publication_lag, ym_to_mi

EVENT_DIR = OUTPUT_DIR / "raw" / "events"
RAIL_PATH = EVENT_DIR / "p6_rail_stations.tsv"
RAIL_LINE_PATH = EVENT_DIR / "p6_rail_lines.tsv"
LEDGER_PATH = OUTPUT_DIR / "66.1.building_ledger_by_dong.txt"
MASTER_PATH = OUTPUT_DIR / "14.1.geocoded_master.txt"
BOUNDARY_PATH = OUTPUT_DIR / "52.2.dong_boundary_match.txt"
EARTH_KM = 6371.0088


def load_complexes():
    """좌표가 있는 아파트 단지를 동별 한 행씩 적재한다."""
    frame = pd.read_csv(MASTER_PATH, sep="\t", dtype=str,
                        usecols=["aptSeq", "umd_name", "lon", "lat"])
    frame["dong"] = frame["aptSeq"].str.split("-").str[0] + "_" + frame["umd_name"]
    frame[["lon", "lat"]] = frame[["lon", "lat"]].apply(pd.to_numeric, errors="coerce")
    return frame.dropna(subset=["dong", "lon", "lat"]).drop_duplicates("aptSeq")


def load_rail():
    """소비 규칙을 만족하는 역 단위 plan·construction·open 사건을 적재한다."""
    raw = pd.read_csv(RAIL_PATH, sep="\t", dtype=str)
    canonical = raw["canonical"].str.lower().eq("true")
    kind = np.select([
        raw["event_type"].eq("plan_announce"),
        raw["event_type"].eq("construction_start")
        & raw["event_subtype"].isin(["physical_work_start", "ceremony"]),
        raw["event_type"].eq("open") & raw["event_status"].eq("actual"),
    ], ["plan", "construction", "open"], default="")
    out = raw[canonical & pd.Series(kind, index=raw.index).ne("")].copy()
    out["kind"] = kind[canonical & pd.Series(kind, index=raw.index).ne("")]
    out["public_month"] = pd.to_datetime(out["public_date"], errors="coerce").dt.to_period("M")
    out[["lat", "lon"]] = out[["lat", "lon"]].apply(pd.to_numeric, errors="coerce")
    out = out.dropna(subset=["public_month", "lat", "lon"]).reset_index(drop=True)
    out["event_id"] = np.arange(len(out))
    out["milestone_id"] = (out["line"].fillna("") + "|" + out["public_date"].fillna("")
                           + "|" + out["kind"])
    return out


def rail_exposure(events=None, complexes=None):
    """각 역 사건 주변 500m·1km에 위치한 동별 단지 share를 계산한다."""
    events = load_rail() if events is None else events
    complexes = load_complexes() if complexes is None else complexes
    lat1 = np.radians(events["lat"].to_numpy())[:, None]
    lon1 = np.radians(events["lon"].to_numpy())[:, None]
    lat2 = np.radians(complexes["lat"].to_numpy())[None, :]
    lon2 = np.radians(complexes["lon"].to_numpy())[None, :]
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    distance = 2 * EARTH_KM * np.arcsin(np.sqrt(a))
    rows = []
    dong_n = complexes.groupby("dong").size()
    for i, event in events.iterrows():
        near = complexes[["dong"]].copy()
        near["within_500"] = distance[i] <= .5
        near["within_1000"] = distance[i] <= 1.
        agg = near.groupby("dong")[["within_500", "within_1000"]].sum()
        agg["exposure_500"] = agg["within_500"] / dong_n
        agg["exposure_1000"] = agg["within_1000"] / dong_n
        part = agg[agg["exposure_1000"] > 0][["exposure_500", "exposure_1000"]].reset_index()
        part["event_id"] = event["event_id"]
        rows.append(part)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def load_supply():
    """strict apartment이면서 사용승인일 QC가 통과한 동×월 세대수 flow를 적재한다."""
    use = ["sigungu_cd", "umd_nm", "hhld_cnt", "use_apr_qc", "use_apr_month", "is_apartment"]
    raw = pd.read_csv(LEDGER_PATH, sep="\t", dtype=str, usecols=use)
    keep = raw["is_apartment"].str.lower().eq("true") & raw["use_apr_qc"].eq("ok")
    out = raw[keep].copy()
    out["dong"] = out["sigungu_cd"] + "_" + out["umd_nm"]
    out["completion_mi"] = ym_to_mi(out["use_apr_month"].str.replace("-", "").astype(int))
    out["households"] = pd.to_numeric(out["hhld_cnt"], errors="coerce").fillna(0)
    return out.groupby(["dong", "sigungu_cd", "completion_mi"], as_index=False)["households"].sum()


def supply_match_counts(supply):
    """52.2 경계 동 key와 맞지 않는 ledger 동·행 수를 센다."""
    boundary = pd.read_csv(BOUNDARY_PATH, sep="\t", dtype=str, usecols=["dong"])
    matched = supply["dong"].isin(set(boundary["dong"]))
    return int((~matched).sum()), int(supply.loc[~matched, "dong"].nunique())


def add_rail_features(panel, events=None, exposure=None):
    """origin 말까지 공개된 사건만 사용해 exposure-weighted rail feature를 붙인다."""
    events = load_rail() if events is None else events
    exposure = rail_exposure(events) if exposure is None else exposure
    joined = exposure.merge(events[["event_id", "kind", "public_month"]], on="event_id")
    joined["event_mi"] = joined["public_month"].map(lambda x: x.year * 12 + x.month - 1)
    out = panel.copy()
    for kind in ("plan", "construction", "open"):
        out[f"rail_{kind}_months"] = 60.
        out[f"rail_{kind}_none"] = 1.
        out[f"rail_{kind}_count12"] = 0.
    out["rail_open_exposure_500"] = 0.
    out["rail_open_exposure_1000"] = 0.
    max_used = np.full(len(out), -1, dtype=int)
    by_dong = {d: g for d, g in joined.groupby("dong")}
    for idx, row in out.iterrows():
        available = by_dong.get(row.dong)
        if available is None:
            continue
        available = available[available.event_mi <= row.mi]
        if available.empty:
            continue
        max_used[idx] = int(available.event_mi.max())
        for kind in ("plan", "construction", "open"):
            part = available[available.kind == kind]
            if part.empty:
                continue
            recent = part[part.event_mi >= row.mi - 11]
            latest = part[part.event_mi == part.event_mi.max()]
            weight = latest.exposure_1000.to_numpy()
            months = row.mi - latest.event_mi.to_numpy()
            out.at[idx, f"rail_{kind}_months"] = min(60., np.average(months, weights=weight))
            out.at[idx, f"rail_{kind}_none"] = 0.
            out.at[idx, f"rail_{kind}_count12"] = recent.exposure_1000.sum()
        opened = available[available.kind == "open"]
        out.at[idx, "rail_open_exposure_500"] = min(1., opened.exposure_500.sum())
        out.at[idx, "rail_open_exposure_1000"] = min(1., opened.exposure_1000.sum())
    used = max_used >= 0
    out["rail_max_public_ym"] = np.where(used, mi_to_ym(max_used), np.nan)
    validate_feature_time_guard(out)
    return out


def add_supply_features(panel, supply=None):
    """t−L까지의 준공 flow rolling sum과 최근 거래량 대비 값을 붙인다."""
    supply = load_supply() if supply is None else supply
    dong_lookup = {(d, int(m)): h for d, m, h in supply[["dong", "completion_mi", "households"]].itertuples(index=False)}
    gu = supply.groupby(["sigungu_cd", "completion_mi"], as_index=False).households.sum()
    gu_lookup = {(g, int(m)): h for g, m, h in gu.itertuples(index=False)}
    out = panel.copy()
    max_used = np.full(len(out), -1, dtype=int)
    supply_by_dong = {d: g for d, g in supply.groupby("dong")}
    supply_by_gu = {str(g): part for g, part in supply.groupby("sigungu_cd")}
    for idx, row in out.iterrows():
        cutoff = int(row.mi - publication_lag(row.mi))
        first = cutoff - 11
        used_dong = supply_by_dong.get(row.dong)
        used_gu = supply_by_gu.get(str(row.sggCd))
        source_months = []
        for source in (used_dong, used_gu):
            if source is not None:
                source_months.extend(source.loc[source.completion_mi.between(first, cutoff),
                                                "completion_mi"].tolist())
        if source_months:
            max_used[idx] = int(max(source_months))
        for months in (3, 6, 12):
            interval = range(cutoff - months + 1, cutoff + 1)
            dong_hh = sum(dong_lookup.get((row.dong, m), 0.) for m in interval)
            gu_hh = sum(gu_lookup.get((str(row.sggCd), m), 0.) for m in interval)
            out.at[idx, f"supply_dong_{months}m"] = np.log1p(dong_hh)
            out.at[idx, f"supply_gu_{months}m"] = np.log1p(gu_hh)
            out.at[idx, f"supply_dong_trade_scaled_{months}m"] = dong_hh / (row.n_12m_feature + 1.)
    used = max_used >= 0
    out["supply_max_completion_ym"] = np.where(used, mi_to_ym(max_used), np.nan)
    validate_feature_time_guard(out)
    return out


def feature_time_audit(panel):
    """origin별 실제 사용 최대월과 point-in-time 위반 건수를 반환한다."""
    audit = panel[["origin", "mi"]].copy()
    audit["rail_max_public_ym"] = panel.get("rail_max_public_ym", np.nan)
    audit["supply_max_completion_ym"] = panel.get("supply_max_completion_ym", np.nan)
    audit["rail_max_public_mi"] = audit.rail_max_public_ym.map(
        lambda value: ym_to_mi(int(value)) if pd.notna(value) else np.nan)
    audit["supply_max_completion_mi"] = audit.supply_max_completion_ym.map(
        lambda value: ym_to_mi(int(value)) if pd.notna(value) else np.nan)
    audit["supply_allowed_mi"] = audit.mi - publication_lag(audit.mi.to_numpy())
    audit["rail_violation"] = audit.rail_max_public_mi.gt(audit.mi)
    audit["supply_violation"] = audit.supply_max_completion_mi.gt(audit.supply_allowed_mi)
    return audit.groupby("origin", as_index=False).agg(
        rail_max_public_mi=("rail_max_public_mi", "max"),
        rail_allowed_mi=("mi", "max"),
        rail_violation_count=("rail_violation", "sum"),
        supply_max_completion_mi=("supply_max_completion_mi", "max"),
        supply_allowed_mi=("supply_allowed_mi", "max"),
        supply_violation_count=("supply_violation", "sum"),
    )


def validate_feature_time_guard(panel):
    """실제 사용월 audit 열이 허용월을 넘으면 즉시 실패한다."""
    audit = feature_time_audit(panel)
    assert audit.rail_violation_count.sum() == 0, "공개일이 origin 뒤인 rail 사건을 사용했다"
    assert audit.supply_violation_count.sum() == 0, "t−L 뒤 completion을 사용했다"
    return audit

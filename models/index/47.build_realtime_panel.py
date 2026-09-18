# ============================================================================
# 47.build_realtime_panel.py
# ============================================================================
# Author:      yjkim
# Purpose:     real-time vintage target과 두 단계 모델 입력 panel을 만든다
# ============================================================================

import time
from pathlib import Path

import numpy as np
import pandas as pd

from _dong_index import RIDGE_LAMBDA, estimate_hedonic_index, load_sales

FIRST_EARLY = pd.Period("2007Q1", freq="Q")
FIRST_TARGET = pd.Period("2008Q1", freq="Q")
FIRST_RELATIVE = pd.Period("2011Q4", freq="Q")
LAST_QUARTER = pd.Period("2026Q2", freq="Q")
LAGS = [1, 2, 4, 8, 12]
HORIZONS = [2, 4, 8, 12]
MIN_SALES_4Q = 20
INDEX_RIDGE_LAMBDA = 5


def assert_dong_keys(frame):
    """동 식별자와 구성 열의 불변식을 확인한다."""
    assert frame["dong"].eq(frame["sggCd"].astype(str) + "_" + frame["umdNm"].astype(str)).all()
    assert frame.groupby("dong")[["sggCd", "umdNm"]].nunique().max().max() == 1


def make_vintage_features(vintage, origin):
    """41과 같은 방식으로 한 vintage의 모멘텀과 eligible를 계산한다."""
    wide = vintage.pivot(index="dong", columns="quarter", values="log_index")
    counts = vintage.pivot(index="dong", columns="quarter", values="n_sales")
    result = vintage.loc[vintage["quarter"] == origin, ["dong", "sggCd", "umdNm"]].set_index("dong")
    result["as_of_quarter"] = origin
    result["n_sales_4q"] = counts.loc[:, origin - 3:origin].sum(axis=1).astype(int)
    for lag in LAGS:
        column = f"mom_{lag}q"
        result[column] = wide[origin] - wide[origin - lag] if origin - lag in wide.columns else np.nan
        result[f"{column}_gu_rel"] = result[column] - result.groupby("sggCd")[column].transform("mean")
    result["eligible"] = result["n_sales_4q"].ge(MIN_SALES_4Q)
    return result.reset_index()


def valid_sale_volume(sales, origins):
    """해제 거래를 제외한 서울·동 4분기 거래량과 log 변화량을 계산한다."""
    rows = []
    counts = sales.groupby(["dong", "quarter"]).size()
    for origin in origins:
        current = counts.loc[counts.index.get_level_values("quarter").isin(pd.period_range(origin - 3, origin, freq="Q"))]
        previous = counts.loc[counts.index.get_level_values("quarter").isin(pd.period_range(origin - 7, origin - 4, freq="Q"))]
        now = current.groupby(level="dong").sum()
        before = previous.groupby(level="dong").sum()
        for dong in now.index.union(before.index):
            n_now, n_before = int(now.get(dong, 0)), int(before.get(dong, 0))
            rows.append({"dong": dong, "as_of_quarter": origin, "sale_n_valid_4q": n_now,
                         "sale_vol_chg": np.log1p(n_now) - np.log1p(n_before)})
    return pd.DataFrame(rows)


def policy_net(events, origins):
    events = events.copy()
    events["quarter"] = pd.PeriodIndex(pd.to_datetime(events["effective_date"]), freq="Q")
    policy = events[events["category"].eq("policy")].copy()
    policy["score"] = policy["direction"].map({"tighten": 1, "ease": -1}).fillna(0)
    return {origin: int(policy.loc[policy["quarter"].isin(pd.period_range(origin - 3, origin, freq="Q")), "score"].sum())
            for origin in origins}


def make_targets(vintage, full_index):
    """E_t 전체에 대해 real-time 및 final-revision target을 만든다."""
    full = full_index.pivot(index="dong", columns="quarter", values="log_index")
    vintage_index = vintage.set_index(["dong", "as_of_quarter"])
    rows = []
    for origin in pd.period_range(FIRST_TARGET, LAST_QUARTER, freq="Q"):
        base = vintage[(vintage["as_of_quarter"] == origin) & vintage["eligible"]]
        for horizon in HORIZONS:
            target_vintage = origin + horizon
            for row in base.itertuples(index=False):
                value, reason = np.nan, "beyond_data"
                if target_vintage <= LAST_QUARTER:
                    try:
                        later = vintage_index.loc[(row.dong, target_vintage)]
                    except KeyError:
                        reason = "no_vintage_row"
                    else:
                        start, end = later.get(f"mom_{horizon}q", np.nan), later.get(f"mom_{horizon}q", np.nan)
                        value = end
                        reason = "none" if np.isfinite(value) else "index_nan"
                full_value = np.nan
                if row.dong in full.index and origin in full.columns and target_vintage in full.columns:
                    full_value = full.loc[row.dong, target_vintage] - full.loc[row.dong, origin]
                rows.append({"dong": row.dong, "sggCd": row.sggCd, "origin": str(origin), "horizon_q": horizon,
                             "target_vintage": str(target_vintage), "eligible_at_origin": True, "y_rt": value,
                             "y_full": full_value, "target_observed": bool(np.isfinite(value)),
                             "target_missing_reason": reason})
    result = pd.DataFrame(rows)
    assert not result.duplicated(["dong", "origin", "horizon_q"]).any()
    return result


def build_panels(vintage, targets, dong_features, macro, sales, events):
    origins = pd.period_range(FIRST_TARGET, LAST_QUARTER, freq="Q")
    volume = valid_sale_volume(sales, origins)
    macro = macro.copy()
    macro["as_of_quarter"] = pd.PeriodIndex(macro["as_of_quarter"], freq="Q")
    macro["sggCd"] = macro["sggCd"].astype(str)
    policy = policy_net(events, origins)
    market_rows, relative_rows = [], []
    features = dong_features.copy()
    features["as_of_quarter"] = pd.PeriodIndex(features["as_of_quarter"], freq="Q")
    targets = targets.copy()
    targets["origin"] = pd.PeriodIndex(targets["origin"], freq="Q")
    for origin in origins:
        base = vintage[(vintage["as_of_quarter"] == origin) & vintage["eligible"]].copy()
        base = base.merge(volume[volume["as_of_quarter"] == origin], on=["dong", "as_of_quarter"], how="left")
        base["sale_n_valid_4q"] = base["sale_n_valid_4q"].fillna(0).astype(int)
        for lag in LAGS:
            base[f"S_mom_{lag}q"] = base[f"mom_{lag}q"].mean()
        base["sale_vol_chg_rel"] = base["sale_vol_chg"] - base["sale_vol_chg"].mean()
        this_macro = macro[macro["as_of_quarter"] == origin]
        rate_chg = float(this_macro["base_rate_change_4q"].iloc[0]) if not this_macro.empty else np.nan
        overheat = float(this_macro["reg_overheated"].mean()) if not this_macro.empty else np.nan
        market = {"origin": str(origin), "n_E": len(base), "rate_chg_4q": rate_chg,
                  "S_sale_vol_4q": int(base["sale_n_valid_4q"].sum()),
                  "S_sale_vol_chg_4q": np.log1p(base["sale_n_valid_4q"].sum()) - np.log1p(
                      volume.loc[volume["as_of_quarter"] == origin - 4, "sale_n_valid_4q"].sum()),
                  "overheated_share": overheat, "policy_net_4q": policy[origin]}
        market.update({f"S_mom_{lag}q": base[f"mom_{lag}q"].mean() for lag in LAGS})
        for horizon in HORIZONS:
            subset = targets[(targets["origin"] == origin) & (targets["horizon_q"] == horizon)]
            rt, full = subset[subset["target_observed"]], subset[np.isfinite(subset["y_full"])]
            market[f"n_T_h{horizon}"] = len(rt)
            market[f"n_U_h{horizon}"] = len(full)
            market[f"M_rt_h{horizon}"] = rt["y_rt"].mean()
            market[f"M_full_h{horizon}"] = full["y_full"].mean()
        market_rows.append(market)
        if origin >= FIRST_RELATIVE:
            rel = base.merge(features, on=["dong", "sggCd", "umdNm", "as_of_quarter"], how="left")
            rel["mom_1q_rel"] = rel["mom_1q"] - rel["S_mom_1q"]
            rel["mom_4q_rel"] = rel["mom_4q"] - rel["S_mom_4q"]
            rel["mom_12q_rel"] = rel["mom_12q"] - rel["S_mom_12q"]
            rel["price_rank"] = rel["sale_ppm2_med_4q"].rank(method="average", pct=True).fillna(0.5)
            rel["jeonse_ratio_rel"] = (rel["jeonse_ratio_4q"] - rel["jeonse_ratio_4q"].median()).fillna(0)
            for col in ["old30_share_4q", "median_age_4q", "jeonse_share_4q", "rent_n_log_change_4q", "mom_2q_gu_rel", "mom_8q_gu_rel"]:
                if col not in rel:
                    rel[col] = np.nan
            rel["origin"] = str(origin)
            relative_rows.append(rel[["dong", "sggCd", "origin"] + RELATIVE_COLUMNS])
    market_panel = pd.DataFrame(market_rows)
    relative = pd.concat(relative_rows, ignore_index=True)
    assert not market_panel.duplicated("origin").any()
    assert not relative.duplicated(["dong", "origin"]).any()
    return market_panel, relative


RELATIVE_COLUMNS = ["mom_1q_rel", "mom_4q_rel", "mom_12q_rel", "price_rank", "jeonse_ratio_rel", "sale_vol_chg_rel",
                    "old30_share_4q", "median_age_4q", "jeonse_share_4q", "rent_n_log_change_4q", "mom_2q_gu_rel", "mom_8q_gu_rel"]


def main():
    root = Path(__file__).resolve().parents[2]
    output = root / "output"
    sales = load_sales(output / "11.1.trades_sale.txt")
    sales = sales[sales["quarter"] <= LAST_QUARTER].reset_index(drop=True)
    later = pd.read_csv(output / "41.1.vintage_momentum.txt", sep="\t", dtype={"dong": str, "sggCd": str, "umdNm": str})
    later["as_of_quarter"] = pd.PeriodIndex(later["as_of_quarter"], freq="Q")
    assert_dong_keys(later)
    frames, started = [], time.time()
    early_origins = pd.period_range(FIRST_EARLY, pd.Period("2011Q3", freq="Q"), freq="Q")
    for i, origin in enumerate(early_origins):
        vintage, diag = estimate_hedonic_index(sales[sales["quarter"] <= origin], ridge_lambda=INDEX_RIDGE_LAMBDA)
        frames.append(make_vintage_features(vintage, origin))
        print(f"처리 중 [{i + 1}/{len(early_origins)}]: {origin} (거래 {diag['n_sales']:,}, 누적 {time.time() - started:.0f}초)")
    early = pd.concat(frames, ignore_index=True)
    early["vintage_source"] = "47_early"
    later["vintage_source"] = "41"
    vintage = pd.concat([early, later], ignore_index=True).sort_values(["dong", "as_of_quarter"]).reset_index(drop=True)
    assert not vintage.duplicated(["dong", "as_of_quarter"]).any()
    assert_dong_keys(vintage)
    full = pd.read_csv(output / "40.1.dong_index.txt", sep="\t", dtype={"dong": str, "sggCd": str, "umdNm": str})
    full["quarter"] = pd.PeriodIndex(full["quarter"], freq="Q")
    targets = make_targets(vintage, full)
    targets["origin"] = pd.PeriodIndex(targets["origin"], freq="Q")
    later_h4 = vintage[vintage["as_of_quarter"] >= pd.Period("2011Q4", freq="Q")][["dong", "as_of_quarter", "mom_4q"]]
    check = targets[(targets["horizon_q"] == 4) & (targets["origin"] >= pd.Period("2007Q4", freq="Q"))].copy()
    check["as_of_quarter"] = check["origin"] + 4
    check = check.merge(later_h4, on=["dong", "as_of_quarter"], how="inner")
    assert np.allclose(check["y_rt"], check["mom_4q"], equal_nan=True)
    features = pd.read_csv(output / "42.1.dong_features.txt", sep="\t", dtype={"dong": str, "sggCd": str, "umdNm": str})
    macro_path = output / "43.1.gu_macro_regulation.txt"
    if not macro_path.exists():
        raise FileNotFoundError(f"필수 입력 없음: {macro_path}")
    macro = pd.read_csv(macro_path, sep="\t", dtype={"sggCd": str})
    events = pd.read_csv(root / "models" / "index" / "event_dates.tsv", sep="\t", dtype=str)
    market, relative = build_panels(vintage, targets, features, macro, sales, events)
    paths = {"vintage": output / "47.1.vintage_momentum_all.txt", "targets": output / "47.2.realtime_targets.txt",
             "market": output / "47.3.seoul_market_panel.txt", "relative": output / "47.4.dong_relative_features.txt"}
    vintage.assign(as_of_quarter=vintage["as_of_quarter"].astype(str)).to_csv(paths["vintage"], sep="\t", index=False, lineterminator="\n")
    targets.assign(origin=targets["origin"].astype(str)).to_csv(paths["targets"], sep="\t", index=False, lineterminator="\n")
    market.to_csv(paths["market"], sep="\t", index=False, lineterminator="\n")
    relative.to_csv(paths["relative"], sep="\t", index=False, lineterminator="\n")
    print("===== 47 panel 생성 완료 =====")
    for path in paths.values(): print(path)


if __name__ == "__main__":
    main()

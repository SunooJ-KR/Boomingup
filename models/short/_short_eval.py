# ============================================================================
# _short_eval.py
# ============================================================================
# Author:      yjkim
# Purpose:     3개월 예측 파일럿(63~65)이 함께 쓰는 panel 적재·feature·지표·bootstrap 함수
# Description: - 기점별 지표를 먼저 계산하고 기점 동일 가중으로 평균한다(계획서 §3.6)
#              - 상대 target r = y − (그 기점 평가 대상 동들의 y 평균)
#              - bootstrap: 기점 moving-block (block 6개월, 2000회, seed 42)
#              - 분기 feature(42.1, 43.1)는 기점 t 이전에 끝난 마지막 분기에서 한 분기 더 늦춘
#                값을 쓴다. 42·43 값이 분기 말 뒤에 공개된 자료를 담을 수 있어서다
# ============================================================================

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from _short_index import LAST_PILOT_ORIGIN, OUTPUT_DIR, mi_to_ym, publication_lag, ym_to_mi

FLAT_BAND = 0.005
EVAL_FIRST, EVAL_LAST = 201201, LAST_PILOT_ORIGIN
PERIODS = {"all": (201201, 202501), "2012-2019": (201201, 201912), "2020-2025.01": (202001, 202501)}
N_NEIGHBORS = 5

FEATURE_GROUPS = {
    "mom_dong": ["mom_0_3", "mom_3_6", "mom_6_12", "mom_0_3_vs_seoul"],
    "mom_area": ["gu_mom_0_3", "gu_mom_3_6", "seoul_mom_0_3", "dong_minus_gu", "nbr_mom_0_3"],
    "volume": ["log_n_3m", "log_n_12m"],
    "jeonse": ["jeonse_ratio_4q", "log_rent_n_4q"],
    "regulation": ["reg_overheated"],
    "redevelop": ["rz_designated_n", "rz_committee_n", "rz_association_n", "rz_implementation_n",
                  "rz_management_n", "rz_construction_n"],
    "completion": ["completed_hh_4q", "completed_hh_8q", "completed_share_8q"],
}
FEATURES = [f for cols in FEATURE_GROUPS.values() for f in cols]


def read_structure():
    summary = pd.read_csv(OUTPUT_DIR / "62.1.structure_summary.txt", sep="\t")
    return summary["recommended"].iloc[0]


def weighted_mean(frame, value, weight, keys):
    ok = frame[value].notna() & frame[weight].gt(0)
    num = (frame[value] * frame[weight]).where(ok).groupby([frame[k] for k in keys]).sum()
    den = frame[weight].where(ok).groupby([frame[k] for k in keys]).sum()
    return num / den


def load_panel(structure):
    """61.1의 target panel을 읽는다. feature는 add_features에서 pastfit으로 붙인다."""
    panel = pd.read_csv(OUTPUT_DIR / "61.1.origin_panel.txt", sep="\t", dtype={"sggCd": str})
    panel = panel[panel["structure"] == structure].copy()
    assert panel["origin"].max() <= LAST_PILOT_ORIGIN
    panel["mi"] = ym_to_mi(panel["origin"])
    return panel.reset_index(drop=True)


def quarter_key(origin, lag_quarters=1):
    """기점 월 t 이전에 끝난 마지막 분기에서 lag_quarters만큼 더 이전 분기 문자열."""
    period = pd.PeriodIndex(pd.to_datetime(origin.astype(str), format="%Y%m"), freq="M")
    done = period.asfreq("Q") - (period.month % 3 != 0).astype(int)
    return (done - lag_quarters).astype(str)


def dong_neighbors():
    """14.1 단지 좌표 평균으로 동 중심을 잡고 가까운 동 5개를 돌려준다."""
    master = pd.read_csv(OUTPUT_DIR / "14.1.geocoded_master.txt", sep="\t", dtype=str,
                         usecols=["aptSeq", "umd_name", "lon", "lat"])
    master["dong"] = master["aptSeq"].str.split("-").str[0] + "_" + master["umd_name"]
    master[["lon", "lat"]] = master[["lon", "lat"]].apply(pd.to_numeric, errors="coerce")
    center = master.dropna(subset=["lon", "lat"]).groupby("dong")[["lon", "lat"]].mean()
    x = center["lon"].to_numpy() * np.cos(np.radians(37.55))
    y = center["lat"].to_numpy()
    dist = np.hypot(x[:, None] - x[None, :], y[:, None] - y[None, :])
    np.fill_diagonal(dist, np.inf)
    nearest = np.argsort(dist, axis=1)[:, :N_NEIGHBORS]
    return {dong: list(center.index[row]) for dong, row in zip(center.index, nearest)}


def _price_features(source):
    """pastfit 행에서 구·서울·인접 모멘텀을 계산한다."""
    out = source.copy()
    for col in ("mom_0_3", "mom_3_6"):
        gu = weighted_mean(out, col, "n_3m", ["origin", "sggCd"]).rename(f"gu_{col}")
        out = out.join(gu, on=["origin", "sggCd"])
    seoul = weighted_mean(out, "mom_0_3", "n_3m", ["origin"]).rename("seoul_mom_0_3")
    out = out.join(seoul, on="origin")
    neighbors = dong_neighbors()
    mom = out.set_index(["origin", "dong"])["mom_0_3"]
    pairs = pd.DataFrame([(d, n) for d, ns in neighbors.items() for n in ns], columns=["dong", "nbr"])
    nbr = out[["origin", "dong"]].merge(pairs, on="dong")
    nbr["nbr_mom"] = mom.reindex(pd.MultiIndex.from_frame(nbr[["origin", "nbr"]])).to_numpy()
    return out.join(nbr.groupby(["origin", "dong"])["nbr_mom"].mean().rename("nbr_mom_0_3"),
                    on=["origin", "dong"])


def add_features(panel, feature_set="MAIN", past_path=None):
    """MAIN·SENS_LAG·SENS_CURRENT 시점 규칙으로 P4 feature를 붙인다."""
    out = panel.copy()
    if past_path is None:
        past_path = OUTPUT_DIR / "61.2.pastfit.txt"
    if feature_set == "SENS_CURRENT":
        source = _price_features(out)
        local = market = volume = source
        local_origin = market_origin = volume_origin = out["mi"]
    else:
        past = pd.read_csv(past_path, sep="\t", dtype={"sggCd": str})
        past["mi"] = ym_to_mi(past["origin"])
        assert (past["max_sale_ym"] <= past["origin"]).all()
        source = _price_features(past)
        lag = publication_lag(out["mi"].to_numpy())
        local_origin = out["mi"] - (3 if feature_set == "MAIN" else lag)
        market_origin = out["mi"] - lag
        volume_origin = market_origin
        def take(origin_values):
            key = pd.MultiIndex.from_arrays([mi_to_ym(origin_values), out["dong"]])
            return source.set_index(["origin", "dong"]).reindex(key).reset_index(drop=True)
        local, market, volume = take(local_origin), take(market_origin), take(volume_origin)

    local_cols = ["mom_0_3", "mom_3_6", "mom_6_12", "gu_mom_0_3", "gu_mom_3_6", "nbr_mom_0_3"]
    for col in local_cols:
        out[col] = local[col].to_numpy()
    out["local_seoul_mom_0_3"] = local["seoul_mom_0_3"].to_numpy()
    out["seoul_mom_0_3"] = market["seoul_mom_0_3"].to_numpy()
    out["n_3m_feature"] = volume["n_3m"].to_numpy()
    out["n_12m_feature"] = volume["n_12m"].to_numpy()
    out["local_max_sale_mi"] = np.asarray(local_origin)
    out["forecast_max_sale_mi"] = np.asarray(market_origin)
    out["mom_0_3_vs_seoul"] = out["mom_0_3"] - out["seoul_mom_0_3"]
    out["dong_minus_gu"] = out["mom_0_3"] - out["gu_mom_0_3"]
    out["log_n_3m"] = np.log1p(out["n_3m_feature"])
    out["log_n_12m"] = np.log1p(out["n_12m_feature"])

    lag = publication_lag(out["mi"].to_numpy())
    if feature_set == "MAIN":
        assert (out["local_max_sale_mi"] <= out["mi"] - 3).all(), "MAIN이 t−3 뒤 거래를 사용했다"
    if feature_set != "SENS_CURRENT":
        assert (out["forecast_max_sale_mi"] <= out["mi"] - lag).all(), "forecast가 t−L 뒤 거래를 사용했다"

    quarter = quarter_key(out["origin"])
    dong_q = pd.read_csv(OUTPUT_DIR / "42.1.dong_features.txt", sep="\t", dtype={"sggCd": str})
    dong_q["log_rent_n_4q"] = np.log1p(dong_q["rent_n_4q"])
    cols = FEATURE_GROUPS["jeonse"] + FEATURE_GROUPS["redevelop"] + FEATURE_GROUPS["completion"]
    out = out.assign(as_of_quarter=quarter).merge(dong_q[["dong", "as_of_quarter"] + cols],
                                                  on=["dong", "as_of_quarter"], how="left")
    gu_q = pd.read_csv(OUTPUT_DIR / "43.1.gu_macro_regulation.txt", sep="\t", dtype={"sggCd": str})
    out = out.merge(gu_q[["sggCd", "as_of_quarter", "reg_overheated"]], on=["sggCd", "as_of_quarter"], how="left")
    return out


def relative(frame, col, by="origin"):
    return frame[col] - frame.groupby(by)[col].transform("mean")


def origin_metrics(frame, pred, y="y"):
    """기점별 MAE, 상대 MAE, Spearman, 방향 정확도(부호·±0.5% 보합)."""
    def one(g):
        p, t = g[pred].to_numpy(), g[y].to_numpy()
        rp, rt = p - p.mean(), t - t.mean()
        sign_ok = np.where(p == 0, np.nan, np.sign(p) == np.sign(t))
        cls = lambda v: np.where(v > FLAT_BAND, 1, np.where(v < -FLAT_BAND, -1, 0))
        rho = spearmanr(p, t)[0] if np.ptp(p) > 0 and len(p) >= 3 else np.nan
        return pd.Series({"n_dongs": len(p), "mae": np.abs(p - t).mean(), "rel_mae": np.abs(rp - rt).mean(),
                          "spearman": rho, "dir_acc": np.nanmean(sign_ok) if np.isfinite(sign_ok).any() else np.nan,
                          "dir_acc_band": (cls(p) == cls(t)).mean()})
    return frame.groupby("origin")[[pred, y]].apply(one)


def interval_coverage(frame, pred, y="y", level=0.8):
    """기점 t에서 target이 t 이전에 끝난(s+3 ≤ t) 과거 잔차의 분위수로 80% 구간을 만든다."""
    resid = (frame[y] - frame[pred]).to_numpy()
    mi = frame["mi"].to_numpy()
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    rows = []
    for origin, idx in frame.groupby("origin").indices.items():
        t = mi[idx[0]]
        past = resid[(mi <= t - 3) & np.isfinite(resid)]
        if len(past) < 100:
            continue
        lo, hi = np.quantile(past, [lo_q, hi_q])
        rows.append({"origin": origin, "coverage": np.mean((resid[idx] >= lo) & (resid[idx] <= hi)),
                     "width": hi - lo})
    return pd.DataFrame(rows).set_index("origin")


def in_period(index, name):
    lo, hi = PERIODS[name]
    return (index >= lo) & (index <= hi)


def block_bootstrap(series, stat=np.mean, block=6, reps=2000, seed=42):
    """시간 순서 Series(또는 DataFrame 행)의 moving-block bootstrap 95% 구간."""
    values = series.to_numpy()
    n = len(values)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(reps, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)).reshape(reps, -1)[:, :n]
    draws = np.array([stat(values[i]) for i in idx])
    return stat(values), np.nanquantile(draws, 0.025), np.nanquantile(draws, 0.975)

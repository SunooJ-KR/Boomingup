# ============================================================================
# _dong6m.py
# ============================================================================
# Author:      yjkim
# Purpose:     법정동 6개월 상대 가격 실험(75~76)의 공통 함수
# Description: 기존 3개월 helper를 수정하지 않고 6개월 target, purge, bootstrap 규칙을 제공한다.
# ============================================================================

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from _short_index import estimate_index, mi_to_ym, publication_lag, ym_to_mi

HORIZON = 6
LAST_ORIGIN = 202501
FIRST_ORIGIN = 200901
EVAL_FIRST = 201201
EVAL_LAST = LAST_ORIGIN
BLOCK_LENGTH = 9
BOOT_REPS = 2000
VOLUME_BINS = [0, 10, 20, 30, 50, np.inf]
VOLUME_LABELS = ["0-9", "10-19", "20-29", "30-49", "50+"]
PERIODS = {
    "all": (201201, 202501),
    "2012-2019": (201201, 201912),
    "2020-2025.01": (202001, 202501),
    "recent_3y": (202202, 202501),
}


def label_periods_6m(window, origin):
    """과거와 미래 거래를 3개월 window 번호로 바꾼다."""
    delta = window["mi"].to_numpy() - origin
    return np.where(delta <= 0, (-delta) // 3, -((delta - 1) // 3 + 1))


def target_rows(window, origin, ridge_lambda=5):
    """W(t+4..t+6)−W(t−2..t) target과 base 거래량을 만든다."""
    frame = window.assign(period=label_periods_6m(window, origin))
    grid = estimate_index(frame, "period", ridge_lambda)
    wide = grid.pivot(index="dong", columns="period", values="log_index")
    get = lambda p: wide[p] if p in wide.columns else pd.Series(np.nan, index=wide.index)
    out = (get(-2) - get(0)).rename("y").to_frame()
    months = frame.groupby(["dong", "mi"]).size().unstack(fill_value=0)

    def count(lo, hi):
        cols = [month for month in months.columns if lo <= month <= hi]
        return months.loc[:, cols].sum(axis=1) if cols else pd.Series(0, index=months.index)

    out["n_3m"] = count(origin - 2, origin)
    out["n_target"] = count(origin + 4, origin + 6)
    out[["n_3m", "n_target"]] = out[["n_3m", "n_target"]].fillna(0).astype(int)
    out = out.join(grid.drop_duplicates("dong").set_index("dong")["sggCd"])
    out["origin"] = int(mi_to_ym(origin))
    return out.reset_index()[["dong", "sggCd", "origin", "y", "n_3m", "n_target"]]


def spearman_brown(value):
    return 2 * value / (1 + value) if np.isfinite(value) and value > -1 else np.nan


def volume_bin(values):
    return pd.cut(values, VOLUME_BINS, right=False, labels=VOLUME_LABELS)


def in_period(index, period):
    lo, hi = PERIODS[period]
    return (index >= lo) & (index <= hi)


def block_bootstrap(values, stat=np.mean, block=BLOCK_LENGTH, reps=BOOT_REPS, seed=42):
    """시간순 origin 값을 9개월 moving block으로 bootstrap한다."""
    array = values.to_numpy() if hasattr(values, "to_numpy") else np.asarray(values)
    n = len(array)
    if n < block:
        return stat(array), np.nan, np.nan
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(reps, n_blocks))
    indexes = (starts[:, :, None] + np.arange(block)).reshape(reps, -1)[:, :n]
    draws = np.asarray([stat(array[index]) for index in indexes])
    return stat(array), np.nanquantile(draws, .025), np.nanquantile(draws, .975)


def relative_metrics(frame, prediction):
    """기점별 relative MAE, Spearman, 방향 정확도를 계산한다."""
    def one(group):
        actual = group["r"].to_numpy()
        pred = group[prediction].to_numpy()
        rho = spearmanr(pred, actual)[0] if len(pred) >= 3 and np.ptp(pred) > 0 else np.nan
        return pd.Series({
            "n_dongs": len(group),
            "rel_mae": np.abs(pred - actual).mean(),
            "spearman": rho,
            "direction_accuracy": (np.sign(pred) == np.sign(actual)).mean(),
        })
    return frame.groupby("origin")[["r", prediction]].apply(one)


def interval_coverage(frame, prediction, level=.8):
    """s+6≤t인 과거 OOT residual만으로 기점별 80% interval을 만든다."""
    work = frame[["origin", "mi", "r", prediction]].dropna().copy()
    work["residual"] = work["r"] - work[prediction]
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    rows = []
    for origin, group in work.groupby("origin"):
        t = int(group["mi"].iloc[0])
        past = work.loc[work["mi"] + HORIZON <= t, "residual"]
        if len(past) < 100:
            continue
        lo, hi = np.quantile(past, [lo_q, hi_q])
        residual = group["residual"].to_numpy()
        rows.append({"origin": origin, "coverage": ((residual >= lo) & (residual <= hi)).mean(),
                     "interval_width": hi - lo})
    return pd.DataFrame(rows).set_index("origin") if rows else pd.DataFrame(columns=["coverage", "interval_width"])


def assert_time_rules(panel):
    """MAIN feature 시점과 sealed holdout을 검증한다."""
    lag = publication_lag(panel["mi"].to_numpy())
    assert panel["origin"].max() <= LAST_ORIGIN, "sealed holdout origin이 포함됐다"
    assert (panel["local_max_sale_mi"] <= panel["mi"] - 3).all(), "동·구 가격이 t−3 뒤 거래를 썼다"
    assert (panel["forecast_max_sale_mi"] <= panel["mi"] - lag).all(), "서울·volume이 t−L 뒤 거래를 썼다"
    assert (ym_to_mi(panel["origin"]) <= ym_to_mi(LAST_ORIGIN)).all()

